"""
CLI script to evaluate RAG retrieval quality.

Example:
    python backend/scripts/eval_rag.py --cases backend/rag/eval_cases.json --k 3
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rag.evaluation import evaluate_retriever, load_eval_cases
from rag.qdrant_store import get_qdrant_client, search_context


def retrieve_chunk_ids(query: str, limit: int) -> list[str]:
    """Retrieve chunk_ids for a query using the production search_context."""
    client = get_qdrant_client()
    if not client:
        print("Qdrant not configured.")
        return []

    # We need ids, so we call the underlying client directly.
    from rag.qdrant_store import _embed, QDRANT_COLLECTION

    embeddings = _embed([query])
    if embeddings is None:
        return []

    response = client.query_points(
        collection_name=QDRANT_COLLECTION,
        query=embeddings[0],
        limit=limit,
        with_payload=True,
    )
    return [
        point.payload.get("chunk_id", str(point.id))
        for point in response.points
        if point.payload
    ]


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate RAG retrieval")
    parser.add_argument("--cases", default="backend/rag/eval_cases.json", type=Path)
    parser.add_argument("--k", type=int, default=3)
    args = parser.parse_args()

    cases = load_eval_cases(args.cases)
    if not cases:
        print(f"No evaluation cases found in {args.cases}")
        return

    metrics = evaluate_retriever(cases, retrieve_chunk_ids, k=args.k)
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
