"""
Ingest the Professor Pepe watermark asset into Qdrant.

Usage:
    cd backend
    source venv/bin/activate
    python scripts/ingest_watermark.py
"""

import os
import sys
from pathlib import Path

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from qdrant_client.http.models import Distance, PointStruct, VectorParams
from rag.qdrant_store import _embed, get_qdrant_client

ASSETS_COLLECTION = os.getenv("ASSETS_COLLECTION", "assets")
VECTOR_SIZE = 3072


def main() -> int:
    client = get_qdrant_client()
    if not client:
        print("❌ Qdrant not configured")
        return 1

    collections = {c.name for c in client.get_collections().collections}
    if ASSETS_COLLECTION not in collections:
        client.create_collection(
            collection_name=ASSETS_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )
        print(f"✅ Created collection '{ASSETS_COLLECTION}'")

    text = (
        "Professor Pepe watermark. A transparent logo overlay used on every image "
        "shared with users. Position: bottom-right. Size: 20% of the image width. "
        "Opacity: 75%. Served from /watermark.png."
    )

    embeddings = _embed([text])
    if embeddings is None:
        print("❌ Embedding failed")
        return 1

    point = PointStruct(
        id=1,
        vector=embeddings[0],
        payload={
            "type": "watermark",
            "path": "/watermark.png",
            "description": text,
            "position": "bottom-right",
            "size_percent": 20,
            "opacity": 0.75,
        },
    )

    client.upsert(collection_name=ASSETS_COLLECTION, points=[point])
    print(f"✅ Watermark asset ingested into '{ASSETS_COLLECTION}'")
    return 0


if __name__ == "__main__":
    sys.exit(main())
