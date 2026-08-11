"""
Strip local paths out of a pepe metadata export before it leaves the machine.

The labelling pipeline records an absolute file_path per image, which carries
the operating-system username and directory layout. That is fine on disk and
never reaches Qdrant — upload_to_qdrant.py does not copy the field — but it
does end up in any copy of the JSON that is shared, committed or uploaded.

Optionally attaches a public url per image, so the deployed app can serve the
pictures from wherever they are hosted instead of depending on a local
directory that is absent from the container.

Usage:
    python scripts/prepare_pepe_metadata.py metadata.json -o metadata.public.json
    python scripts/prepare_pepe_metadata.py metadata.json -o out.json \\
        --base-url https://example.org/pepes/
"""

import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import quote

# Fields that describe where a file sits on the machine that produced the JSON.
LOCAL_PATH_FIELDS = ("file_path", "path", "local_path", "source_path", "abs_path")

# Anything that looks like a home directory, on any platform.
HOME_PATH = re.compile(r"(/Users/|/home/|[A-Za-z]:\\\\Users\\\\)[^\"'\s]*")


def _scrub(value):
    """Remove home-directory paths from any string nested in the value."""
    if isinstance(value, str):
        return HOME_PATH.sub("<redacted>", value)
    if isinstance(value, list):
        return [_scrub(v) for v in value]
    if isinstance(value, dict):
        return {k: _scrub(v) for k, v in value.items()}
    return value


def prepare(source: Path, target: Path, base_url: str | None) -> int:
    data = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        print("❌ Expected an object keyed by filename.")
        return 1

    removed = 0
    scrubbed = 0
    out: dict = {}

    for filename, entry in data.items():
        if not isinstance(entry, dict):
            out[filename] = entry
            continue

        clean = {}
        for key, value in entry.items():
            if key in LOCAL_PATH_FIELDS:
                removed += 1
                continue
            new_value = _scrub(value)
            if new_value != value:
                scrubbed += 1
            clean[key] = new_value

        if base_url:
            clean["url"] = base_url.rstrip("/") + "/" + quote(filename)

        out[filename] = clean

    target.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")

    # Prove it rather than assert it: re-read what was written and look again.
    written = target.read_text(encoding="utf-8")
    leftovers = HOME_PATH.findall(written)

    print(f"Entries         : {len(out)}")
    print(f"Path fields removed : {removed}")
    print(f"Strings scrubbed    : {scrubbed}")
    if base_url:
        print(f"url added           : {len(out)}  (e.g. {next(iter(out.values())).get('url')})")
    print(f"Wrote               : {target}")
    print()
    if leftovers:
        print(f"⚠️  {len(leftovers)} home paths still present, e.g. {leftovers[0]}")
        return 1
    print("✅ No home-directory paths remain in the output.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sanitise a pepe metadata export")
    parser.add_argument("source", type=Path)
    parser.add_argument("-o", "--out", type=Path, required=True)
    parser.add_argument(
        "--base-url",
        help="Public prefix for the images; adds a url field per entry.",
    )
    args = parser.parse_args()
    sys.exit(prepare(args.source, args.out, args.base_url))
