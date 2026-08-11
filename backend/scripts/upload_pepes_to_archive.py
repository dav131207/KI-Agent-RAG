"""
Upload the labelled pepe images to an Internet Archive item.

The Qdrant payload names a file but not where it lives, so the app falls back to
MEMES_DIR — a directory that is not in the container image and not on the
persistent volume. Hosting the pictures publicly and writing their url into the
payload removes that dependency entirely.

The upload is driven from metadata.json so exactly the images the collection
knows about are sent, under exactly the filenames it stores. Nothing else in
the source folders goes up, and the remote name always matches the payload.

Prerequisites:
    pip install internetarchive
    ia configure            # or set IA_ACCESS_KEY / IA_SECRET_KEY

Usage:
    python scripts/upload_pepes_to_archive.py metadata.json --identifier my-pepes
    python scripts/upload_pepes_to_archive.py metadata.json --identifier my-pepes --apply

Afterwards:
    python scripts/backfill_pepe_urls.py \\
        --base-url https://archive.org/download/my-pepes --apply
"""

import argparse
import json
import os
import sys
from pathlib import Path

BASE_DOWNLOAD_URL = "https://archive.org/download"


def _load_targets(metadata_path: Path) -> tuple[list[tuple[str, Path]], list[str]]:
    """Return (remote_name, local_path) pairs plus the names whose file is gone."""
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    targets, missing = [], []
    for filename, entry in data.items():
        local = entry.get("file_path") if isinstance(entry, dict) else None
        candidate = Path(local) if local else metadata_path.parent / filename
        if candidate.is_file():
            targets.append((filename, candidate))
        else:
            missing.append(filename)
    return targets, missing


def upload(metadata_path: Path, identifier: str, apply: bool, title: str) -> int:
    targets, missing = _load_targets(metadata_path)
    total_bytes = sum(p.stat().st_size for _, p in targets)

    print(f"Item identifier : {identifier}")
    print(f"Files to upload : {len(targets)}  ({total_bytes / 1024 / 1024:.1f} MB)")
    if missing:
        print(f"⚠️  Missing locally: {len(missing)}  e.g. {missing[0]}")
    print(f"Resulting prefix: {BASE_DOWNLOAD_URL}/{identifier}")
    print()

    if not targets:
        print("Nothing to upload.")
        return 1

    if not apply:
        for name, path in targets[:3]:
            print(f"  would upload {path.name}  ->  {name}")
        print("\nDry run — nothing uploaded. Re-run with --apply to publish.")
        print("Note: this makes the images publicly downloadable and is not")
        print("easily undone; the item stays in the Archive's history.")
        return 0

    try:
        from internetarchive import upload as ia_upload
    except ImportError:
        print("❌ internetarchive is not installed.  pip install internetarchive")
        return 1

    access = os.getenv("IA_ACCESS_KEY")
    secret = os.getenv("IA_SECRET_KEY")
    credentials = {"access_key": access, "secret_key": secret} if access and secret else {}

    metadata = {
        "title": title,
        "mediatype": "image",
        "collection": "opensource_media",
        # No local paths and no personal data: only the picture files go up.
        "description": "Community Pepe image collection used by the Professor Pepe agent.",
    }

    failed = 0
    for index, (name, path) in enumerate(targets, start=1):
        try:
            responses = ia_upload(
                identifier,
                files={name: str(path)},
                metadata=metadata if index == 1 else None,
                retries=3,
                **credentials,
            )
            ok = all(r.status_code in (200, None) for r in responses)
            if not ok:
                failed += 1
                print(f"  ❌ {name}")
        except Exception as exc:
            failed += 1
            print(f"  ❌ {name}: {exc}")
        if index % 50 == 0:
            print(f"  … {index}/{len(targets)}")

    print()
    print(f"✅ Uploaded {len(targets) - failed}/{len(targets)}; {failed} failed.")
    print(f"Now run: python scripts/backfill_pepe_urls.py "
          f"--base-url {BASE_DOWNLOAD_URL}/{identifier} --apply")
    return 1 if failed else 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Upload pepe images to archive.org")
    parser.add_argument("metadata", type=Path)
    parser.add_argument("--identifier", required=True, help="Archive item id, e.g. rare-pepes-pepecoin")
    parser.add_argument("--title", default="Rare Pepe Collection")
    parser.add_argument("--apply", action="store_true", help="Upload; otherwise dry run")
    args = parser.parse_args()
    sys.exit(upload(args.metadata, args.identifier, args.apply, args.title))
