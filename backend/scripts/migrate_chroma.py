"""
Migrate documents from a ChromaDB JSON export into the Qdrant collection
used by Professor Pepe.

The script re-embeds the documents with the embedding model configured in
rag.qdrant_store (default: models/gemini-embedding-001) so the vectors match
the search model.

Usage:
    cd backend
    QDRANT_URL=./qdrant_storage venv/bin/python scripts/migrate_chroma.py \
        /path/to/chroma_export.json

Environment variables:
    GEMINI_API_KEY      required for embeddings
    QDRANT_URL          Qdrant Cloud URL, :memory:, or local path
    QDRANT_API_KEY      only for Qdrant Cloud
    QDRANT_COLLECTION   defaults to professor_pepe
"""

import json
import os
import sys
from pathlib import Path

# Make the backend package importable when running from scripts/.
backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from rag.qdrant_store import _embed, ensure_collection, get_qdrant_client
from qdrant_client.http.models import PointStruct


def load_export(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, dict):
        # Accept the raw ChromaDB `get()` shape as well.
        records = []
        ids = data.get("ids", [])
        docs = data.get("documents", [])
        metas = data.get("metadatas", [])
        for i in range(len(ids)):
            records.append({
                "id": ids[i],
                "text": docs[i] if i < len(docs) else "",
                "metadata": metas[i] if i < len(metas) else {},
            })
        return records
    return data


def migrate(path: Path, batch_size: int = 32) -> int:
    if not ensure_collection():
        print("❌ Could not connect to Qdrant or create collection.")
        print("   Make sure QDRANT_URL is set (e.g. ./qdrant_storage or your Qdrant Cloud URL).")
        return 1

    client = get_qdrant_client()
    records = load_export(path)
    print(f"📦 Loaded {len(records)} records from {path}")

    existing = client.count(collection_name=os.getenv("QDRANT_COLLECTION", "professor_pepe")).count
    offset = existing

    total = 0
    for i in range(0, len(records), batch_size):
        batch = records[i : i + batch_size]
        texts = [r["text"] for r in batch]
        embeddings = _embed(texts)
        if embeddings is None:
            print("❌ Embedding failed. Is GEMINI_API_KEY set?")
            return 1

        points = [
            PointStruct(
                id=offset + i + j,
                vector=embeddings[j],
                payload={
                    "text": batch[j]["text"],
                    "source": batch[j].get("metadata", {}).get("source", "chroma_migration"),
                    **batch[j].get("metadata", {}),
                },
            )
            for j in range(len(batch))
        ]
        client.upsert(collection_name=os.getenv("QDRANT_COLLECTION", "professor_pepe"), points=points)
        total += len(points)
        print(f"   Migrated batch {i + 1}-{i + len(batch)}")

    print(f"✅ Migrated {total} chunks into Qdrant (collection: {os.getenv('QDRANT_COLLECTION', 'professor_pepe')})")
    try:
        client.close()
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <chroma_export.json>")
        sys.exit(1)

    export_path = Path(sys.argv[1]).expanduser()
    if not export_path.exists():
        print(f"❌ File not found: {export_path}")
        sys.exit(1)

    sys.exit(migrate(export_path))
