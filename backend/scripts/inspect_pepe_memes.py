"""
Report what is actually stored in the `pepe_memes` collection.

The ingest scripts in this repository embed the single phrase "rare pepe meme"
once and reuse that vector for every image, which makes semantic search over
them meaningless — every point sits at the same distance from any query. A
collection filled by some other process may well be labelled properly, and only
the live collection can settle it.

Usage:
    cd backend
    venv/bin/python scripts/inspect_pepe_memes.py [--sample 300]

Reads QDRANT_URL / QDRANT_API_KEY from the environment or .env.
"""

import argparse
import sys
from collections import Counter
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(backend_dir))

from rag.qdrant_store import PEPE_MEMES_COLLECTION, get_qdrant_client  # noqa: E402


def _vector_of(point) -> tuple:
    """Return a point's vector as a hashable tuple, or () when absent."""
    vector = getattr(point, "vector", None)
    if isinstance(vector, dict):  # named vectors
        vector = next(iter(vector.values()), None)
    return tuple(vector) if vector else ()


def inspect(sample_size: int) -> int:
    client = get_qdrant_client()
    if not client:
        print("❌ No Qdrant client. Set QDRANT_URL (and QDRANT_API_KEY for Cloud).")
        return 1

    try:
        total = client.count(collection_name=PEPE_MEMES_COLLECTION).count
    except Exception as exc:
        print(f"❌ Could not read collection '{PEPE_MEMES_COLLECTION}': {exc}")
        return 1

    print(f"Collection    : {PEPE_MEMES_COLLECTION}")
    print(f"Points total  : {total:,}")
    if total == 0:
        return 0

    points, offset = [], None
    while len(points) < sample_size:
        page, offset = client.scroll(
            collection_name=PEPE_MEMES_COLLECTION,
            limit=min(256, sample_size - len(points)),
            offset=offset,
            with_payload=True,
            with_vectors=True,
        )
        if not page:
            break
        points.extend(page)
        if offset is None:
            break

    n = len(points)
    print(f"Sampled       : {n}")
    print()

    descriptions = [(p.payload or {}).get("description", "") for p in points]
    explanations = [(p.payload or {}).get("explanation", "") for p in points]
    filenames = [(p.payload or {}).get("filename", "") for p in points]
    vectors = [_vector_of(p) for p in points]
    have_vectors = [v for v in vectors if v]

    unique_desc = len(set(descriptions))
    unique_vec = len(set(have_vectors))

    print(f"distinct descriptions : {unique_desc} of {n}")
    print(f"distinct explanations : {len(set(explanations))} of {n}")
    print(f"distinct filenames    : {len(set(filenames))} of {n}")
    print(f"distinct vectors      : {unique_vec} of {len(have_vectors)}")
    print()

    payload_keys = Counter(k for p in points for k in (p.payload or {}))
    print("payload fields:", dict(payload_keys))
    print()

    print("most common descriptions:")
    for text, count in Counter(descriptions).most_common(3):
        print(f'  {count:>5}x  "{(text or "")[:90]}"')
    print()

    # The two failure modes are independent: identical text defeats the keyword
    # half of the hybrid search, identical vectors defeat the semantic half.
    if unique_vec <= 1 and len(have_vectors) > 1:
        print("VERDICT: every point shares one vector — semantic search cannot")
        print("         rank these at all; results are effectively arbitrary.")
    elif unique_vec < len(have_vectors) * 0.5:
        print("VERDICT: vectors are largely duplicated — search will be weak.")
    else:
        print("VERDICT: vectors are distinct — semantic search is meaningful.")

    if unique_desc <= 1 and n > 1:
        print("         Descriptions are identical too, so the keyword pass")
        print("         cannot discriminate either.")
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect the pepe_memes collection")
    parser.add_argument("--sample", type=int, default=300)
    sys.exit(inspect(parser.parse_args().sample))
