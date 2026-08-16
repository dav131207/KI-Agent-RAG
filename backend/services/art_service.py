"""Community Art service for Professor Pepe."""

import hashlib
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
    # Lets the picker offer stills and animations separately. Stored rather
    # than derived per query so filtering is a plain WHERE.
    "media_type": "TEXT NOT NULL DEFAULT 'image'",
    # Content hash, so the same picture uploaded twice is recognised whatever
    # it was named. Not UNIQUE: rows that predate the column share an empty
    # value, and a unique index would refuse to be created over them.
    "content_hash": "TEXT NOT NULL DEFAULT ''",
}

MEDIA_TYPES = ("image", "gif", "video")

_EXTENSION_MEDIA = {
    ".gif": "gif",
    ".mp4": "video",
    ".webm": "video",
}


def hash_file(path: Path) -> str:
    """Content hash of a file, or an empty string if it cannot be read."""
    try:
        digest = hashlib.blake2b(digest_size=16)
        with open(path, "rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return ""


def hash_bytes(data: bytes) -> str:
    """Content hash of data already in memory."""
    return hashlib.blake2b(data, digest_size=16).hexdigest()


def find_by_hash(content_hash: str) -> Optional[dict]:
    """The piece already holding this exact content, if any."""
    if not content_hash:
        return None
    row = _get_conn().execute(
        "SELECT * FROM community_art WHERE content_hash = ? LIMIT 1", (content_hash,)
    ).fetchone()
    return dict(row) if row else None


def media_type_for(filename: str) -> str:
    """Classify a file by extension; anything else is a still image."""
    return _EXTENSION_MEDIA.get(Path(filename).suffix.lower(), "image")


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
    added = set()
    for column, definition in _RATING_COLUMNS.items():
        if column not in existing:
            conn.execute(f"ALTER TABLE community_art ADD COLUMN {column} {definition}")
            added.add(column)

    if "content_hash" in added:
        # Existing files are hashed once so art uploaded before the column
        # existed still takes part in duplicate detection.
        for row in conn.execute("SELECT id, filename, status FROM community_art"):
            directory = (
                MEMES_COMMUNITY_DIR if row["status"] == "approved" else UPLOADS_DIR
            )
            digest = hash_file(directory / row["filename"])
            if digest:
                conn.execute(
                    "UPDATE community_art SET content_hash = ? WHERE id = ?",
                    (digest, row["id"]),
                )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_art_hash ON community_art(content_hash)"
        )

    if "media_type" in added:
        # Rows that predate the column all carry the 'image' default, which is
        # wrong for every GIF and video already uploaded. Classify them once.
        for row in conn.execute("SELECT id, filename FROM community_art"):
            conn.execute(
                "UPDATE community_art SET media_type = ? WHERE id = ?",
                (media_type_for(row["filename"]), row["id"]),
            )

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

def add_art(
    filename: str,
    label: str,
    file_path: Path,
    mime_type: str,
    content_hash: str = "",
) -> dict:
    description = generate_description(file_path, mime_type)
    conn = _get_conn()
    cur = conn.cursor()
    media = media_type_for(filename)
    cur.execute(
        "INSERT INTO community_art (filename, label, description, status, created_at,"
        " media_type, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (filename, label, description, "pending", int(time.time()), media,
         content_hash or hash_file(file_path))
    )
    conn.commit()
    return {
        "id": cur.lastrowid,
        "filename": filename,
        "label": label,
        "description": description,
        "status": "pending",
        "media_type": media,
    }

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

    Each entry carries a per-media breakdown so the picker can offer stills and
    animations separately without a round trip per switch.
    """
    conn = _get_conn()
    rows = conn.execute(
        """
        SELECT label,
               media_type,
               COUNT(*) AS pieces,
               SUM(ups) AS ups,
               SUM(downs) AS downs
        FROM community_art
        WHERE status = 'approved'
        GROUP BY label, media_type
        """
    ).fetchall()

    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        entry = grouped.setdefault(
            row["label"],
            {
                "label": row["label"],
                "count": 0,
                "ups": 0,
                "downs": 0,
                "media": {media: 0 for media in MEDIA_TYPES},
            },
        )
        entry["count"] += row["pieces"]
        entry["ups"] += row["ups"] or 0
        entry["downs"] += row["downs"] or 0
        # An unknown media_type would otherwise be silently dropped from the
        # breakdown while still counting towards the total.
        media = row["media_type"] if row["media_type"] in MEDIA_TYPES else "image"
        entry["media"][media] += row["pieces"]

    labels = []
    for entry in grouped.values():
        labels.append(
            {
                "label": entry["label"],
                "count": entry["count"],
                "score": _wilson_lower_bound(entry["ups"], entry["downs"]),
                "media": entry["media"],
            }
        )
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


def get_random_art(label: str, media: Optional[str] = None) -> Optional[dict]:
    """
    Pick an approved piece for a label, favouring what the community rated well.

    Sampling is weighted rather than top-scoring: always showing the current
    best would bury everything else permanently and stop new ratings arriving.
    `media` narrows the pool to one of MEDIA_TYPES; None means any.
    """
    conn = _get_conn()
    query = "SELECT * FROM community_art WHERE status = 'approved' AND label = ?"
    params: list[Any] = [label]
    if media in MEDIA_TYPES:
        query += " AND media_type = ?"
        params.append(media)

    rows = conn.execute(query, params).fetchall()
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


def record_impression(art_id: int, sequence: bool = True) -> None:
    """
    Count that a piece was shown, so exploration and rates have a base.

    `sequence` advances the "shown last" counter. A shortlist displays several
    pieces at once, and marking all of them as the most recent would make the
    no-repeat rule exclude an arbitrary one of them from the next single draw.
    """
    conn = _get_conn()
    if sequence:
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
    else:
        conn.execute(
            "UPDATE community_art SET impressions = impressions + 1, last_shown_at = ?"
            " WHERE id = ?",
            (int(time.time()), art_id),
        )
    conn.commit()


# Words carried by almost every post, so matching on them would rank by post
# length rather than by subject.
_STOPWORDS = frozenset("""
a an and are as at be been but by can do does for from get got had has have he
her his how i if in into is it its just like me more most my no not of off on
one only or our out over own she so some such than that the their them then
there these they this those to too up us was we were what when where which who
why will with you your
der die das und ist sind ein eine einen einem eines dem den des auf aus bei mit
nach von vor zu zum zur im in ist es sich auch nicht noch nur oder aber wie was
wer wo wenn dann als am an für über unter durch gegen ohne um sehr mehr
""".split())


def _tokens(text: str) -> set:
    """Content words, lowercased. Handles, hashtags and URLs are noise here."""
    import re

    text = re.sub(r"https?://\S+", " ", text or "")
    text = re.sub(r"[@#$]\w+", " ", text)
    return {
        word
        for word in re.findall(r"[a-zA-ZäöüßÄÖÜ]{3,}", text.lower())
        if word not in _STOPWORDS
    }


# How far the community rating may move a suggestion. Small on purpose: it
# should separate two comparable matches, never lift a well-liked piece above
# one that actually fits the post.
RATING_INFLUENCE = 0.25


def suggest_art(text: str, limit: int = 4, media: Optional[str] = None) -> dict:
    """
    Shortlist approved community art that fits a piece of text.

    Scored on word overlap against the Gemini description and the label rather
    than by embedding: the library is small enough that a scan costs nothing,
    and an embedding call here would add hundreds of milliseconds to a post
    that has already been generated.

    Falls back to the best-rated pieces when nothing matches, so the picker is
    never empty — the caller is told which happened.
    """
    conn = _get_conn()
    query = "SELECT * FROM community_art WHERE status = 'approved'"
    params: list[Any] = []
    if media in MEDIA_TYPES:
        query += " AND media_type = ?"
        params.append(media)
    rows = conn.execute(query, params).fetchall()
    if not rows:
        return {"art": [], "matched_on": "empty", "matched_count": 0}

    wanted = _tokens(text)
    scored = []
    for row in rows:
        rating = _wilson_lower_bound(row["ups"] or 0, row["downs"] or 0)
        candidate = _tokens(f"{row['description'] or ''} {row['label']}")
        overlap = wanted & candidate
        # Normalised by the candidate's vocabulary so a long, rambling
        # description does not outrank a precise one just by covering more
        # ground.
        keyword = len(overlap) / math.sqrt(len(candidate)) if candidate else 0.0
        scored.append((keyword + RATING_INFLUENCE * rating, keyword, row))

    matched = sorted(
        (entry for entry in scored if entry[1] > 0), key=lambda e: e[0], reverse=True
    )
    rest = sorted(
        (entry for entry in scored if entry[1] == 0), key=lambda e: e[0], reverse=True
    )

    # Padded with the best-rated remainder when few pieces share wording with
    # the post. One suggestion is not a choice, and the point of the shortlist
    # is that the author picks. The count says how many actually matched, so
    # the picker can be honest about which part of the row is a match.
    pool = (matched + rest)[:limit]

    return {
        "art": [
            {
                "id": row["id"],
                "filename": row["filename"],
                "label": row["label"],
                "description": row["description"],
                "media_type": row["media_type"],
                "matched": keyword > 0,
                "score": round(total, 4),
            }
            for total, keyword, row in pool
        ],
        "matched_on": "context" if matched else "rating",
        "matched_count": min(len(matched), limit),
    }


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
