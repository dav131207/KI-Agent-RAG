"""
Hybrid retrieval with reciprocal rank fusion (RRF).

Combines dense vector search with a simple keyword/BM25-style search over
payload text. RRF merges the two ranked lists without requiring calibrated
scores, which is useful when vector and keyword scores live on different
scales.
"""

import re
from typing import List, Optional

from qdrant_client import QdrantClient


def _keyword_score(query: str, text: str) -> float:
    """
    Simple BM25-ish score based on exact token matches.

    This is intentionally lightweight: it does not require an external
    indexer and works on the payload text stored in Qdrant.
    """
    query_tokens = set(re.findall(r"\b\w+\b", query.lower()))
    text_tokens = re.findall(r"\b\w+\b", text.lower())
    if not query_tokens or not text_tokens:
        return 0.0

    text_freq = {}
    for token in text_tokens:
        text_freq[token] = text_freq.get(token, 0) + 1

    score = 0.0
    for token in query_tokens:
        if token in text_freq:
            # Simple TF component; length-normalised roughly by text token count.
            score += text_freq[token] / len(text_tokens)
    return score


def _keyword_search(
    client: QdrantClient,
    collection_name: str,
    query: str,
    limit: int = 20,
) -> List[tuple[str, float]]:
    """Search all payloads by keyword score and return top-k (text, score)."""
    if not query.strip():
        return []

    try:
        points = client.scroll(
            collection_name=collection_name,
            with_payload=True,
            limit=1000,
        )[0]
    except Exception:
        return []

    scored = []
    for point in points:
        text = point.payload.get("text", "") if point.payload else ""
        score = _keyword_score(query, text)
        if score > 0:
            scored.append((point.id, score))

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def reciprocal_rank_fusion(
    vector_results: List[tuple],
    keyword_results: List[tuple],
    k: float = 60.0,
) -> List[tuple]:
    """
    Merge two ranked lists by Reciprocal Rank Fusion.

    Each result is identified by its id (first element of the tuple).
    Returns the merged list ordered by RRF score, descending.
    """
    scores: dict = {}

    for rank, item in enumerate(vector_results):
        item_id = item[0]
        scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, item in enumerate(keyword_results):
        item_id = item[0]
        scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)

    # Preserve original tuples in a lookup dict.
    lookup = {item[0]: item for item in vector_results + keyword_results}

    ranked_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [lookup[item_id] for item_id, _ in ranked_ids if item_id in lookup]


def merge_hybrid_results(
    vector_points: List,
    keyword_ranked_ids: List[tuple],
    final_limit: int = 3,
) -> List:
    """
    Take Qdrant vector points and keyword-ranked ids and return a fused,
    re-ranked list of points.
    """
    vector_results = [(p.id, p) for p in vector_points]
    keyword_results = keyword_ranked_ids

    fused = reciprocal_rank_fusion(vector_results, keyword_results)
    return [item[1] for item in fused[:final_limit]]
