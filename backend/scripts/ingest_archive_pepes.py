"""
Ingest rare pepe image URLs from the Internet Archive's PepeImgurAlbum
into the Qdrant `pepe_memes` collection.

The album is a ZIP file served by archive.org. Its directory listing page
contains direct links to every image. This script parses those links and
stores the HTTPS URLs as Qdrant payloads, so the deployed app can proxy and
watermark them without needing local image files.

Usage:
    cd backend
    python scripts/ingest_archive_pepes.py

Environment variables (see backend/.env.example):
    GEMINI_API_KEY      required for embeddings
    QDRANT_URL          Qdrant Cloud URL, :memory:, or local path
    QDRANT_API_KEY      only for Qdrant Cloud
"""

import os
import re
import sys
import urllib.parse
from pathlib import Path

import httpx
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

ARCHIVE_LIST_URL = "https://archive.org/download/PepeImgurAlbum/Pepe%20-%20Imgur.zip/?format=json"
ARCHIVE_BASE = "https://archive.org/download/PepeImgurAlbum/Pepe%20-%20Imgur.zip/"
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"}


def fetch_image_urls() -> list[str]:
    """Scrape the archive.org ZIP directory listing for direct image URLs."""
    r = httpx.get(ARCHIVE_LIST_URL, follow_redirects=True, timeout=120)
    r.raise_for_status()

    # The listing page contains rows like:
    # <a href="//archive.org/download/PepeImgurAlbum/Pepe%20-%20Imgur.zip/0001%20-%20D7rMzsQ.gif">
    pattern = re.compile(
        r'<a href="//archive\.org/download/PepeImgurAlbum/Pepe%20-%20Imgur\.zip/([^"]+)"'
    )

    seen = set()
    urls: list[str] = []
    for match in pattern.finditer(r.text):
        filename = urllib.parse.unquote(match.group(1))
        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_EXTENSIONS:
            continue
        if filename in seen:
            continue
        seen.add(filename)
        urls.append(ARCHIVE_BASE + urllib.parse.quote(filename, safe="/"))

    return urls


def ingest(urls: list[str], recreate: bool = True, batch_size: int = 100) -> int:
    if not ensure_pepe_memes_collection(recreate=recreate):
        print("❌ Could not connect to Qdrant or create collection.")
        print("   Make sure QDRANT_URL and GEMINI_API_KEY are set.")
        return 1

    client = get_qdrant_client()
    if not client:
        print("❌ Qdrant client not available.")
        return 1

    if not urls:
        print("❌ No image URLs found in archive listing.")
        return 1

    print(f"📦 Found {len(urls)} image URLs in PepeImgurAlbum")

    # A single shared embedding keeps semantic search simple and avoids
    # thousands of Vision API calls.
    description = "rare pepe meme"
    embeddings = _embed([description])
    if embeddings is None:
        print("❌ Embedding failed. Is GEMINI_API_KEY set correctly?")
        return 1
    vector = embeddings[0]

    total = 0
    for batch_start in range(0, len(urls), batch_size):
        batch = urls[batch_start : batch_start + batch_size]
        points: list[PointStruct] = []
        for offset, image_url in enumerate(batch):
            idx = batch_start + offset
            filename = image_url.split("/")[-1]
            points.append(
                PointStruct(
                    id=idx,
                    vector=vector,
                    payload={
                        "url": image_url,
                        "filename": filename,
                        "description": description,
                        "explanation": "A rare pepe from the Internet Archive (PepeImgurAlbum).",
                        "is_politically_sensitive": False,
                        "source": "PepeImgurAlbum (Internet Archive)",
                    },
                )
            )

        client.upsert(collection_name=PEPE_MEMES_COLLECTION, points=points)
        total += len(points)
        print(f"   Ingested {total}/{len(urls)}")

    print(f"✅ Ingested {total} URLs into Qdrant (collection: {PEPE_MEMES_COLLECTION})")
    try:
        client.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    image_urls = fetch_image_urls()
    sys.exit(ingest(image_urls, recreate=True))
