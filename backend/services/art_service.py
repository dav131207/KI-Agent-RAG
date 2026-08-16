"""Community Art service for Professor Pepe."""

import math
import random
import shutil
import sqlite3
import threading
import time
from io import BytesIO
from pathlib import Path
from typing import Any, Optional

from core.config import (
    BACKEND_DIR,
    COMMUNITY_ART_DIR,
    GEMINI_API_KEY,
    UPLOADS_DIR as CONFIG_UPLOADS_DIR,
)

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

DB_PATH = BACKEND_DIR / "data" / "analytics.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = CONFIG_UPLOADS_DIR
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

# Approved art used to be moved to backend/memes/community, which is outside the
# persistent volume: approving a piece moved its file off the disk and the next
# deploy deleted it, while its database row kept claiming it was approved.
MEMES_COMMUNITY_DIR = COMMUNITY_ART_DIR
MEMES_COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)

_LEGACY_COMMUNITY_DIR = BACKEND_DIR / "memes" / "community"


def _migrate_legacy_community_files() -> None:
    """Move approved art left in the pre-disk location onto the volume."""
    if not _LEGACY_COMMUNITY_DIR.is_dir():
        return
    for old in _LEGACY_COMMUNITY_DIR.iterdir():
        if not old.is_file():
            continue
        target = MEMES_COMMUNITY_DIR / old.name
        if target.exists():
            continue
        try:
            shutil.move(str(old), str(target))
        except Exception:
            pass

_local = threading.local()

def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

# Columns added after the table shipped. Existing deployments carry rows
# without them, so they are applied as migrations rather than being folded into
# the CREATE — an installed database is never recreated.
_RATING_COLUMNS = {
    "impressions": "INTEGER NOT NULL DEFAULT 0",
    "ups": "INTEGER NOT NULL DEFAULT 0",
    "downs": "INTEGER NOT NULL DEFAULT 0",
    "last_shown_at": "INTEGER NOT NULL DEFAULT 0",
    # Ordering the pieces by last_shown_at cannot answer "which was shown last"
    # because its resolution is one second, and several pieces are shown inside
    # the same second. This counter increments once per impression, so the
    # ordering is exact. last_shown_at stays for display in the dashboard.
    "shown_seq": "INTEGER NOT NULL DEFAULT 0",
}


def init_db() -> None:
    conn = _get_conn()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS community_art (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            filename TEXT NOT NULL,
            label TEXT NOT NULL,
            description TEXT,
            status TEXT DEFAULT 'pending',
            created_at INTEGER NOT NULL
        )
        """
    )
    existing = {row["name"] for row in conn.execute("PRAGMA table_info(community_art)")}
    for column, definition in _RATING_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE community_art ADD COLUMN {column} {definition}")
    conn.commit()

init_db()
_migrate_legacy_community_files()

def _describable_bytes(file_path: Path, mime_type: str) -> tuple[bytes, str]:
    """
    Return image data in a form the vision model accepts.

    Gemini takes PNG, JPEG and WEBP for images but not GIF, so an uploaded GIF
    came back with a failure message instead of a description. A single frame
    describes the picture well enough — the middle one rather than the first,
    which in a lot of animations is blank or a fade-in.
    """
    data = file_path.read_bytes()
    if mime_type != "image/gif":
        return data, mime_type

    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as animation:
            animation.seek(getattr(animation, "n_frames", 1) // 2)
            buf = BytesIO()
            animation.convert("RGB").save(buf, format="PNG")
            return buf.getvalue(), "image/png"
    except Exception:
        return data, mime_type


def generate_description(file_path: Path, mime_type: str) -> str:
    """Generate a description of the image/video using Gemini."""
    if not genai or not GEMINI_API_KEY:
        return "Gemini API not configured. No description generated."

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        data, mime_type = _describable_bytes(file_path, mime_type)

        response = client.models.generate_content(
            model="gemini-3.6-flash",
            contents=[
                types.Content(
                    role="user",
                    parts=[
                        types.Part.from_bytes(data=data, mime_type=mime_type),
                        types.Part.from_text(text="Describe this image/GIF/video briefly (1-3 sentences) as if you are summarizing it for a Pepecoin community member.")
                    ]
                )
            ],
        )
        return response.text or "No description generated."
    except Exception as e:
        return f"Failed to generate description: {e}"

def add_art(filename: str, label: str, file_path: Path, mime_type: str) -> dict:
    description = generate_description(file_path, mime_type)
    conn = _get_conn()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO community_art (filename, label, description, status, created_at) VALUES (?, ?, ?, ?, ?)",
        (filename, label, description, "pending", int(time.time()))
    )
    conn.commit()
    return {"id": cur.lastrowid, "filename": filename, "label": label, "description": description, "status": "pending"}

def get_all_art() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM community_art ORDER BY created_at DESC").fetchall()
    return [dict(row) for row in rows]

def update_art(art_id: int, status: str, label: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM community_art WHERE id = ?", (art_id,)).fetchone()
    if not row:
        return None
    
    import shutil
    
    filename = row["filename"]
    # If moving to approved, move file from uploads to memes/community
    if status == "approved" and row["status"] != "approved":
        src = UPLOADS_DIR / filename
        dest = MEMES_COMMUNITY_DIR / filename
        if src.exists():
            shutil.move(str(src), str(dest))
    elif status != "approved" and row["status"] == "approved":
        # If moving back to pending/rejected, move back
        src = MEMES_COMMUNITY_DIR / filename
        dest = UPLOADS_DIR / filename
        if src.exists():
            shutil.move(str(src), str(dest))

    conn.execute(
        "UPDATE community_art SET status = ?, label = ? WHERE id = ?",
        (status, label, art_id)
    )
    conn.commit()
    row = conn.execute("SELECT * FROM community_art WHERE id = ?", (art_id,)).fetchone()
    return dict(row) if row else None

def get_labels() -> list[dict]:
    """
    Approved categories, best-regarded first.

    SELECT DISTINCT returned them in whatever order SQLite happened to produce,
    which put a category holding one unrated piece above one holding thirty
    well-rated ones. Ordering by how the community actually rated the contents
    makes the list a ranking instead of a dump.
    """
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT label,
               COUNT(*) AS pieces,
               SUM(ups) AS ups,
               SUM(downs) AS downs
        FROM community_art
        WHERE status = 'approved'
        GROUP BY label
        """
    ).fetchall()

    labels = [
        {
            "label": row["label"],
            "count": row["pieces"],
            "score": _wilson_lower_bound(row["ups"] or 0, row["downs"] or 0),
        }
        for row in rows
    ]
    labels.sort(key=lambda item: (-item["score"], -item["count"], item["label"].lower()))
    return labels

# How a piece earns its place. Unrated art keeps a real chance (BASE_WEIGHT) so
# the pool never freezes around whatever happened to be rated first, and art
# nobody has seen yet is pushed until it has been shown often enough to be
# judged — without that, a piece that is never shown can never be rated, and
# never being rated is what keeps it from being shown.
BASE_WEIGHT = 0.2
RATED_BONUS = 2.0
EXPLORATION_IMPRESSIONS = 5
EXPLORATION_BONUS = 0.3

# Art the community has actually rejected. Held back rather than deleted: the
# rating is a signal, not a verdict, and you can still see it in the dashboard.
SUPPRESS_MIN_VOTES = 4
SUPPRESS_BELOW = 0.15
SUPPRESSED_WEIGHT = 0.02


def _wilson_lower_bound(ups: int, downs: int, z: float = 1.96) -> float:
    """
    Lower bound of the 95% confidence interval on the approval rate.

    A plain ups/(ups+downs) ratio makes one thumbs-up on one view (100%) beat
    forty-nine on fifty (98%), which would hand the top slot to whatever was
    rated least. The bound discounts by how little is known, so confidence has
    to be earned with volume.
    """
    n = ups + downs
    if n == 0:
        return 0.0
    p = ups / n
    denominator = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * n)) / n)
    return max(0.0, (centre - margin) / denominator)


def _selection_weight(row: sqlite3.Row) -> float:
    """Score one piece for weighted sampling."""
    ups = row["ups"] or 0
    downs = row["downs"] or 0
    score = _wilson_lower_bound(ups, downs)

    if ups + downs >= SUPPRESS_MIN_VOTES and score < SUPPRESS_BELOW:
        return SUPPRESSED_WEIGHT

    weight = BASE_WEIGHT + RATED_BONUS * score
    if (row["impressions"] or 0) < EXPLORATION_IMPRESSIONS:
        weight += EXPLORATION_BONUS
    return weight


def get_random_art(label: str) -> Optional[dict]:
    """
    Pick an approved piece for a label, favouring what the community rated well.

    Sampling is weighted rather than top-scoring: always showing the current
    best would bury everything else permanently and stop new ratings arriving.
    """
    conn = _get_conn()
    rows = conn.execute(
        "SELECT * FROM community_art WHERE status = 'approved' AND label = ?",
        (label,),
    ).fetchall()
    if not rows:
        return None

    # Never repeat the piece that was just shown, unless it is the only one.
    if len(rows) > 1:
        most_recent = max(rows, key=lambda r: r["shown_seq"] or 0)
        if (most_recent["shown_seq"] or 0) > 0:
            rows = [r for r in rows if r["id"] != most_recent["id"]]

    weights = [_selection_weight(r) for r in rows]
    total = sum(weights)
    chosen = random.choices(rows, weights=weights, k=1)[0] if total > 0 else random.choice(rows)
    return dict(chosen)


def record_impression(art_id: int) -> None:
    """Count that a piece was shown, so exploration and rates have a base."""
    conn = _get_conn()
    conn.execute(
        """
        UPDATE community_art
        SET impressions = impressions + 1,
            last_shown_at = ?,
            shown_seq = (SELECT COALESCE(MAX(shown_seq), 0) + 1 FROM community_art)
        WHERE id = ?
        """,
        (int(time.time()), art_id),
    )
    conn.commit()


def record_art_vote(art_id: int, feedback: str) -> bool:
    """Attribute a thumbs rating to the artwork that was on screen."""
    column = {"thumbs_up": "ups", "thumbs_down": "downs"}.get(feedback)
    if column is None:
        return False
    conn = _get_conn()
    cur = conn.execute(
        f"UPDATE community_art SET {column} = {column} + 1 WHERE id = ?", (art_id,)
    )
    conn.commit()
    return cur.rowcount > 0

def delete_art(art_id: int) -> bool:
    conn = _get_conn()
    row = conn.execute("SELECT * FROM community_art WHERE id = ?", (art_id,)).fetchone()
    if not row:
        return False
    
    filename = row["filename"]
    # Try deleting from both directories just in case
    for d in (UPLOADS_DIR, MEMES_COMMUNITY_DIR):
        file_path = d / filename
        if file_path.exists():
            try:
                file_path.unlink()
            except Exception:
                pass

    conn.execute("DELETE FROM community_art WHERE id = ?", (art_id,))
    conn.commit()
    return True
