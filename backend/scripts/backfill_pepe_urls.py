"""
Attach a public image url to each point in `pepe_memes`.

The payload carries only a filename, so the app resolves pictures through
MEMES_DIR — a directory that is absent from the container image and not on the
persistent volume, which means a deployed instance has no file to serve. Giving
each point a url removes that dependency: _extract_pepe_image_url already looks
for one and prefers it over the local path.

This only writes the url field. It never deletes, re-embeds or reorders
anything, so the labelling stays exactly as it is.

Usage:
    cd backend
    venv/bin/python scripts/backfill_pepe_urls.py --base-url https://example.org/pepes/
    venv/bin/python scripts/backfill_pepe_urls.py --base-url ... --apply
"""

import argparse
import sys
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

load_dotenv()

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from rag.qdrant_store import PEPE_MEMES_COLLECTION, get_qdrant_client  # noqa: E402


def backfill(base_url: str, apply: bool, batch_size: int = 100) -> int:
    client = get_qdrant_client()
    if not client:
        print("❌ No Qdrant client. Set QDRANT_URL (and QDRANT_API_KEY for Cloud).")
        return 1

    prefix = base_url.rstrip("/")
    updated = skipped = missing = 0
    offset = None
    preview = []

    while True:
        points, offset = client.scroll(
            collection_name=PEPE_MEMES_COLLECTION,
            limit=batch_size,
            offset=offset,
            with_payload=True,
            with_vectors=False,
        )
        if not points:
            break

        for point in points:
            payload = point.payload or {}
            filename = payload.get("filename")
            if not filename:
                missing += 1
                continue
            if payload.get("url"):
                skipped += 1
                continue

            url = f"{prefix}/{quote(str(filename))}"
            if len(preview) < 3:
                preview.append(url)
            if apply:
                # set_payload merges: the existing fields are left untouched.
                client.set_payload(
                    collection_name=PEPE_MEMES_COLLECTION,
                    payload={"url": url},
                    points=[point.id],
                )
            updated += 1

        if offset is None:
            break

    print(f"Collection      : {PEPE_MEMES_COLLECTION}")
    print(f"Would set url   : {updated}")
    print(f"Already had url : {skipped}")
    print(f"No filename     : {missing}")
    for url in preview:
        print(f"  e.g. {url}")
    print()
    if not apply:
        print("Dry run — nothing written. Re-run with --apply to commit.")
    else:
        print("✅ Payloads updated. Vectors and existing fields untouched.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Add image urls to pepe_memes")
    parser.add_argument("--base-url", required=True, help="Public prefix for the images")
    parser.add_argument("--apply", action="store_true", help="Write; otherwise dry run")
    args = parser.parse_args()
    sys.exit(backfill(args.base_url, args.apply))
