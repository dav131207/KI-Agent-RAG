"""
Lightweight SQLite analytics for Professor Pepe.

Tracks user interactions, feedback, conversions, latency and device info.
Designed to be easy to swap for PostgreSQL later.
"""

import hashlib
import json
import re
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional

DB_PATH = Path(__file__).resolve().parent / "data" / "analytics.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

_local = threading.local()


def _get_conn() -> sqlite3.Connection:
    """Return a thread-local SQLite connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn


def init_db() -> None:
    """Create the analytics tables if they do not exist."""
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            session_hash TEXT NOT NULL,
            session_id TEXT,
            event_type TEXT NOT NULL,
            command TEXT,
            message TEXT,
            language TEXT,
            country TEXT,
            user_agent TEXT,
            device_type TEXT,
            os TEXT,
            browser TEXT,
            feedback TEXT,
            conversion_type TEXT,
            latency_ms INTEGER,
            topic_keywords TEXT,
            metadata TEXT,
            created_at INTEGER NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_event_type ON events(event_type)
        """
    )
    conn.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_events_session ON events(session_id)
        """
    )
    
    try:
        conn.execute("ALTER TABLE events ADD COLUMN user_message TEXT")
    except sqlite3.OperationalError:
        pass  # column already exists
        
    try:
        conn.execute("ALTER TABLE events ADD COLUMN wallet_address TEXT")
    except sqlite3.OperationalError:
        pass

    # Re-enable foreign keys after migrations
    conn.execute("PRAGMA foreign_keys = ON")
    conn.commit()


def _hash_ip(ip: Optional[str]) -> str:
    """Create a stable, anonymised session identifier from an IP address."""
    if not ip:
        return "unknown"
    return hashlib.sha256(ip.encode("utf-8")).hexdigest()[:16]


def _extract_keywords(text: Optional[str]) -> list[str]:
    """Extract simple topic keywords from a message for clustering."""
    if not text:
        return []
    text = text.lower()
    # Remove common stopwords
    stopwords = {
        "the", "a", "an", "is", "are", "was", "were", "be", "been", "being",
        "have", "has", "had", "do", "does", "did", "will", "would", "could",
        "should", "may", "might", "must", "shall", "can", "need", "dare",
        "ought", "used", "to", "of", "in", "for", "on", "with", "at", "by",
        "from", "as", "into", "through", "during", "before", "after", "above",
        "below", "between", "under", "and", "but", "or", "yet", "so", "if",
        "because", "although", "though", "while", "where", "when", "that",
        "which", "who", "whom", "whose", "what", "this", "these", "those",
        "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
        "them", "my", "your", "his", "its", "our", "their", "mine", "yours",
        "pepecoin", "pepe", "professor", "fren", "please", "how", "what", "can",
        "tell", "about", "want", "get", "make", "create", "give", "show",
    }
    words = re.findall(r"\b[a-z]{3,}\b", text)
    keywords = [w for w in words if w not in stopwords]
    # Return top 5 unique keywords by frequency
    freq = {}
    for w in keywords:
        freq[w] = freq.get(w, 0) + 1
    sorted_words = sorted(freq.items(), key=lambda x: x[1], reverse=True)
    return [w for w, _ in sorted_words[:5]]


def track_event(
    client_ip: Optional[str],
    event_type: str,
    command: Optional[str] = None,
    message: Optional[str] = None,
    language: Optional[str] = None,
    country: Optional[str] = None,
    session_id: Optional[str] = None,
    user_agent: Optional[str] = None,
    feedback: Optional[str] = None,
    conversion_type: Optional[str] = None,
    latency_ms: Optional[int] = None,
    metadata: Optional[dict[str, Any]] = None,
    user_message: Optional[str] = None,
    wallet_address: Optional[str] = None,
) -> None:
    """Persist a single analytics event."""
    conn = _get_conn()
    now = datetime.utcnow()

    device_type = os = browser = None
    if user_agent:
        ua = user_agent.lower()
        device_type = "mobile" if any(x in ua for x in ["mobile", "android", "iphone"]) else "desktop"
        if "windows" in ua:
            os = "Windows"
        elif "mac" in ua:
            os = "macOS"
        elif "linux" in ua:
            os = "Linux"
        elif "android" in ua:
            os = "Android"
        elif "iphone" in ua or "ipad" in ua:
            os = "iOS"

        if "chrome" in ua and "edg" not in ua:
            browser = "Chrome"
        elif "safari" in ua and "chrome" not in ua:
            browser = "Safari"
        elif "firefox" in ua:
            browser = "Firefox"
        elif "edg" in ua:
            browser = "Edge"

    topic_keywords = None
    if event_type in ("chat_message", "message_send") and message:
        topic_keywords = json.dumps(_extract_keywords(message))

    conn.execute(
        """
        INSERT INTO events
        (timestamp, session_hash, session_id, event_type, command, message, language, country,
         user_agent, device_type, os, browser, feedback, conversion_type, latency_ms,
         topic_keywords, metadata, created_at, user_message, wallet_address)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            now.isoformat(),
            _hash_ip(client_ip),
            session_id,
            event_type,
            command,
            message,
            language,
            country,
            user_agent,
            device_type,
            os,
            browser,
            feedback,
            conversion_type,
            latency_ms,
            topic_keywords,
            json.dumps(metadata) if metadata else None,
            int(now.timestamp()),
            user_message,
            wallet_address,
        ),
    )
    conn.commit()


def get_summary(days: int = 7) -> dict[str, Any]:
    """Return aggregated analytics for the last N days."""
    conn = _get_conn()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    total_events = conn.execute(
        "SELECT COUNT(*) FROM events WHERE timestamp >= ?", (since,)
    ).fetchone()[0]

    unique_sessions = conn.execute(
        "SELECT COUNT(DISTINCT session_hash) FROM events WHERE timestamp >= ?", (since,)
    ).fetchone()[0]

    unique_cookies = conn.execute(
        "SELECT COUNT(DISTINCT session_id) FROM events WHERE timestamp >= ? AND session_id IS NOT NULL",
        (since,),
    ).fetchone()[0]

    command_counts = {
        row["command"]: row["count"]
        for row in conn.execute(
            """
            SELECT command, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND event_type = 'command_click' AND command IS NOT NULL
            GROUP BY command
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    language_counts = {
        row["language"] or "unknown": row["count"]
        for row in conn.execute(
            """
            SELECT language, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND language IS NOT NULL
            GROUP BY language
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    country_counts = {
        row["country"] or "unknown": row["count"]
        for row in conn.execute(
            """
            SELECT country, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND country IS NOT NULL
            GROUP BY country
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    device_counts = {
        row["device_type"] or "unknown": row["count"]
        for row in conn.execute(
            """
            SELECT device_type, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND device_type IS NOT NULL
            GROUP BY device_type
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    os_counts = {
        row["os"] or "unknown": row["count"]
        for row in conn.execute(
            """
            SELECT os, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND os IS NOT NULL
            GROUP BY os
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    feedback_counts = {
        row["feedback"]: row["count"]
        for row in conn.execute(
            """
            SELECT feedback, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND feedback IS NOT NULL
            GROUP BY feedback
            """,
            (since,),
        )
    }

    conversion_counts = {
        row["conversion_type"]: row["count"]
        for row in conn.execute(
            """
            SELECT conversion_type, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND conversion_type IS NOT NULL
            GROUP BY conversion_type
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    daily_events = [
        {"date": row["date"], "count": row["count"]}
        for row in conn.execute(
            """
            SELECT date(timestamp) as date, COUNT(*) as count
            FROM events
            WHERE timestamp >= ?
            GROUP BY date(timestamp)
            ORDER BY date DESC
            """,
            (since,),
        )
    ]

    top_topics = [
        {"keyword": row["keyword"], "count": row["count"]}
        for row in conn.execute(
            """
            SELECT json_each.value AS keyword, COUNT(*) as count
            FROM events, json_each(topic_keywords)
            WHERE timestamp >= ? AND topic_keywords IS NOT NULL
            GROUP BY keyword
            ORDER BY count DESC
            LIMIT 20
            """,
            (since,),
        )
    ]

    recent_feedback = [
        {
            "timestamp": row["timestamp"],
            "feedback": row["feedback"],
            "message": row["message"],
            "user_message": row["user_message"],
        }
        for row in conn.execute(
            """
            SELECT timestamp, feedback, message, user_message
            FROM events
            WHERE timestamp >= ? AND event_type = 'feedback' AND message IS NOT NULL
            ORDER BY timestamp DESC
            LIMIT 50
            """,
            (since,),
        )
    ]

    rag_row = conn.execute(
        """
        SELECT
            SUM(CASE WHEN CAST(json_extract(metadata, '$.chunk_count') AS INTEGER) = 0 THEN 1 ELSE 0 END) as no_context,
            SUM(CASE WHEN CAST(json_extract(metadata, '$.chunk_count') AS INTEGER) > 0 THEN 1 ELSE 0 END) as with_context,
            COUNT(*) as total
        FROM events
        WHERE timestamp >= ? AND event_type = 'rag_retrieval'
        """,
        (since,),
    ).fetchone()
    rag_total = rag_row["total"] or 0
    rag_coverage = {
        "with_context": rag_row["with_context"] or 0,
        "no_context": rag_row["no_context"] or 0,
        "total": rag_total,
        "coverage_pct": round((rag_row["with_context"] or 0) / rag_total * 100) if rag_total else None,
    }

    feedback_by_rag_context: dict[str, dict[str, int]] = {}
    for row in conn.execute(
        """
        SELECT
            CASE WHEN CAST(json_extract(metadata, '$.rag_chunk_count') AS INTEGER) > 0
                 THEN 'with_context' ELSE 'no_context' END as bucket,
            feedback,
            COUNT(*) as count
        FROM events
        WHERE timestamp >= ? AND event_type = 'feedback'
              AND json_extract(metadata, '$.rag_chunk_count') IS NOT NULL
        GROUP BY bucket, feedback
        """,
        (since,),
    ):
        feedback_by_rag_context.setdefault(row["bucket"], {})[row["feedback"]] = row["count"]

    error_counts = {
        row["command"] or "unknown": row["count"]
        for row in conn.execute(
            """
            SELECT command, COUNT(*) as count
            FROM events
            WHERE timestamp >= ? AND event_type = 'error'
            GROUP BY command
            ORDER BY count DESC
            """,
            (since,),
        )
    }

    recent_errors = [
        {
            "timestamp": row["timestamp"],
            "command": row["command"],
            "message": row["message"],
            "metadata": json.loads(row["metadata"]) if row["metadata"] else None,
        }
        for row in conn.execute(
            """
            SELECT timestamp, command, message, metadata
            FROM events
            WHERE timestamp >= ? AND event_type = 'error'
            ORDER BY timestamp DESC
            LIMIT 30
            """,
            (since,),
        )
    ]

    avg_latency = conn.execute(
        """
        SELECT AVG(latency_ms) FROM events
        WHERE timestamp >= ? AND latency_ms IS NOT NULL
        """,
        (since,),
    ).fetchone()[0]

    return {
        "days": days,
        "total_events": total_events,
        "unique_sessions": unique_sessions,
        "unique_cookies": unique_cookies,
        "command_counts": command_counts,
        "language_counts": language_counts,
        "country_counts": country_counts,
        "device_counts": device_counts,
        "os_counts": os_counts,
        "feedback_counts": feedback_counts,
        "conversion_counts": conversion_counts,
        "top_topics": top_topics,
        "avg_latency_ms": round(avg_latency) if avg_latency else None,
        "daily_events": daily_events,
        "recent_feedback": recent_feedback,
        "rag_coverage": rag_coverage,
        "feedback_by_rag_context": feedback_by_rag_context,
        "error_counts": error_counts,
        "recent_errors": recent_errors,
    }


def get_feedback_export(days: int = 90) -> list[dict[str, Any]]:
    """Return every feedback event in the window, shaped for RAG evaluation pipelines.

    Each record pairs the user's question with the response it was rated on,
    so a downstream pipeline can split "good" vs "bad" outputs directly.
    """
    conn = _get_conn()
    since = (datetime.utcnow() - timedelta(days=days)).isoformat()

    rows = conn.execute(
        """
        SELECT timestamp, feedback, message, user_message, language, session_id, metadata
        FROM events
        WHERE timestamp >= ? AND event_type = 'feedback' AND message IS NOT NULL
        ORDER BY timestamp ASC
        """,
        (since,),
    )
    records = []
    for row in rows:
        meta = json.loads(row["metadata"]) if row["metadata"] else {}
        records.append(
            {
                "timestamp": row["timestamp"],
                "question": row["user_message"],
                "response": row["message"],
                "feedback": row["feedback"],
                "language": row["language"],
                "session_id": row["session_id"],
                "rag_chunk_count": meta.get("rag_chunk_count"),
            }
        )
    return records


# Initialise the database on import.
init_db()
