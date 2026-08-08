"""Community Art service for Professor Pepe."""

import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from core.config import BACKEND_DIR, GEMINI_API_KEY

try:
    from google import genai
    from google.genai import types
except ImportError:
    genai = None
    types = None

DB_PATH = BACKEND_DIR / "data" / "analytics.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

UPLOADS_DIR = BACKEND_DIR / "data" / "uploads"
UPLOADS_DIR.mkdir(parents=True, exist_ok=True)

MEMES_COMMUNITY_DIR = BACKEND_DIR / "memes" / "community"
MEMES_COMMUNITY_DIR.mkdir(parents=True, exist_ok=True)

_local = threading.local()

def _get_conn() -> sqlite3.Connection:
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

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
    conn.commit()

init_db()

def generate_description(file_path: Path, mime_type: str) -> str:
    """Generate a description of the image/video using Gemini."""
    if not genai or not GEMINI_API_KEY:
        return "Gemini API not configured. No description generated."
    
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        with open(file_path, "rb") as f:
            data = f.read()
            
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

def get_labels() -> list[str]:
    conn = _get_conn()
    rows = conn.execute("SELECT DISTINCT label FROM community_art WHERE status = 'approved'").fetchall()
    return [row["label"] for row in rows]

def get_random_art(label: str) -> Optional[dict]:
    conn = _get_conn()
    row = conn.execute(
        "SELECT * FROM community_art WHERE status = 'approved' AND label = ? ORDER BY RANDOM() LIMIT 1",
        (label,)
    ).fetchone()
    return dict(row) if row else None

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
