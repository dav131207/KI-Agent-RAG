"""
Ingest local rare pepe images into the Qdrant `pepe_memes` collection.

Each image becomes one Qdrant point with a shared embedding for the phrase
"rare pepe meme". This keeps semantic search functional (any pepe-related
query returns a candidate) while avoiding thousands of Gemini Vision API calls.

Usage:
    cd backend
    venv/bin/python scripts/ingest_rare_pepes.py

Environment variables:
    GEMINI_API_KEY      required for embeddings
    QDRANT_URL          Qdrant Cloud URL, :memory:, or local path
    QDRANT_API_KEY      only for Qdrant Cloud
    MEMES_DIR           directory containing rare pepe images (default: ./memes)
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from qdrant_client.http.models import PointStruct

from rag.qdrant_store import (
    PEPE_MEMES_COLLECTION,
    _embed,
    ensure_pepe_memes_collection,
    get_qdrant_client,
)


WIPE_CONFIRM_ENV = "ALLOW_PEPE_MEMES_WIPE"


def _confirm_wipe() -> None:
    """Refuse to drop pepe_memes unless it was explicitly allowed.

    The collection is filled by an external labelling pipeline — one embedding
    per image from its description, OCR text, keywords and mood. Re-running an
    ingest script here replaced all of it with a single shared vector, silently
    destroying work these scripts cannot reproduce.
    """
    if os.getenv(WIPE_CONFIRM_ENV, "").lower() not in ("1", "true", "yes"):
        print(f"\n\u26d4 Refusing to delete '{PEPE_MEMES_COLLECTION}'.")
        print("   It may hold per-image labels that this script cannot rebuild.")
        print(f"   Check first:  python scripts/inspect_pepe_memes.py")
        print(f"   Override with: {WIPE_CONFIRM_ENV}=1\n")
        raise SystemExit(1)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def list_memes(memes_dir: Path) -> list[Path]:
    if not memes_dir.is_dir():
        return []
    files = [
        f
        for f in memes_dir.iterdir()
        if f.is_file() and f.suffix.lower() in IMAGE_EXTENSIONS
    ]
    return sorted(files)


def ingest(memes_dir: Path, recreate: bool = True) -> int:
    if recreate:
        _confirm_wipe()
    if not ensure_pepe_memes_collection(recreate=recreate):
        print("❌ Could not connect to Qdrant or create collection.")
        print("   Make sure QDRANT_URL and GEMINI_API_KEY are set.")
        return 1

    client = get_qdrant_client()
    files = list_memes(memes_dir)
    if not files:
        print(f"❌ No image files found in {memes_dir}")
        return 1

    print(f"📦 Found {len(files)} rare pepes in {memes_dir}")

    # Embed the generic search phrase once and reuse it for every image.
    description = "rare pepe meme"
    embeddings = _embed([description])
    if embeddings is None:
        print("❌ Embedding failed. Is GEMINI_API_KEY set correctly?")
        return 1
    vector = embeddings[0]

    batch_size = 100
    total = 0
    for batch_start in range(0, len(files), batch_size):
        batch_files = files[batch_start : batch_start + batch_size]
        points = []
        for offset, file_path in enumerate(batch_files):
            idx = batch_start + offset
            points.append(
                PointStruct(
                    id=idx,
                    vector=vector,
                    payload={
                        "filename": file_path.name,
                        "file_path": str(file_path.relative_to(memes_dir.parent)),
                        "description": description,
                        "explanation": "A rare pepe from the community archive.",
                        "is_politically_sensitive": False,
                        "source": "PepeImgurAlbum (Internet Archive)",
                    },
                )
            )

        client.upsert(collection_name=PEPE_MEMES_COLLECTION, points=points)
        total += len(points)
        print(f"   Ingested batch {batch_start + 1}-{batch_start + len(batch_files)}")

    print(f"✅ Ingested {total} rare pepes into Qdrant (collection: {PEPE_MEMES_COLLECTION})")
    try:
        client.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    memes_dir = Path(os.getenv("MEMES_DIR", "./memes")).expanduser()
    if not memes_dir.is_absolute():
        memes_dir = backend_dir / memes_dir

    sys.exit(ingest(memes_dir))
