"""
Ingest every markdown file under backend/knowledge/ into the live Qdrant
knowledge base, through the admin /ingest/file endpoint.

The knowledge lives in the repo so it is versioned and can be re-ingested
at any time; the ingestion itself runs against the deployed server because
that is where the Qdrant and Gemini credentials are. Re-running after an
edit is safe: the endpoint drops every point of that file before writing
the new chunks, so nothing stale stays retrievable.

Usage:
    ADMIN_TOKEN=... python backend/scripts/ingest_knowledge.py
    ADMIN_TOKEN=... python backend/scripts/ingest_knowledge.py knowledge/one-file.md

Environment:
    ADMIN_TOKEN   required, the server's admin bearer token
    API_BASE      optional, defaults to the Render deployment
"""

import os
import sys
from pathlib import Path

import httpx

API_BASE = os.getenv("API_BASE", "https://professor-pepe-agent.onrender.com").rstrip("/")
KNOWLEDGE_DIR = Path(__file__).resolve().parent.parent / "knowledge"


def main(argv: list[str]) -> int:
    token = os.getenv("ADMIN_TOKEN")
    if not token:
        print("❌ ADMIN_TOKEN is not set")
        return 1

    if argv:
        files = [Path(a) for a in argv]
    else:
        files = sorted(p for p in KNOWLEDGE_DIR.glob("*.md") if p.is_file())
    if not files:
        print(f"❌ No markdown files found in {KNOWLEDGE_DIR}")
        return 1

    failed = 0
    with httpx.Client(timeout=120) as client:
        for path in files:
            # The source name is what shows up in the Qdrant payload, so keep
            # it stable and path-free: re-ingesting from another checkout must
            # hit the same points.
            name = path.name
            resp = client.post(
                f"{API_BASE}/api/ingest/file",
                headers={"Authorization": f"Bearer {token}"},
                files={"file": (name, path.read_bytes(), "text/markdown")},
            )
            if resp.status_code == 200:
                print(f"✅ {name}: {resp.json().get('ingested_chunks')} chunks")
            else:
                failed += 1
                print(f"❌ {name}: HTTP {resp.status_code} {resp.text[:200]}")

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
