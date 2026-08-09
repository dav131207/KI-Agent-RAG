"""
Hybrid retrieval with reciprocal rank fusion (RRF).

Combines dense vector search with a simple keyword/BM25-style search over
payload text. RRF merges the two ranked lists without requiring calibrated
scores, which is useful when vector and keyword scores live on different
scales.
"""

import re
from typing import Any, List

from qdrant_client import QdrantClient

# Upper bound on how many payloads the keyword pass will scan. Qdrant's scroll
# API is paginated, so this is the total across pages, not a single request.
KEYWORD_SCAN_LIMIT = 10_000
KEYWORD_SCAN_PAGE_SIZE = 1_000


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
) -> List[tuple[Any, float, Any]]:
    """
    Search payloads by keyword score and return top-k (id, score, record).

    The record is carried along so the caller can fuse keyword-only hits with
    vector hits without a second round-trip to Qdrant.
    """
    if not query.strip():
        return []

    scored: List[tuple[Any, float, Any]] = []
    offset = None
    scanned = 0

    try:
        while scanned < KEYWORD_SCAN_LIMIT:
            page_size = min(KEYWORD_SCAN_PAGE_SIZE, KEYWORD_SCAN_LIMIT - scanned)
            points, offset = client.scroll(
                collection_name=collection_name,
                with_payload=True,
                limit=page_size,
                offset=offset,
            )
            if not points:
                break

            scanned += len(points)
            for point in points:
                text = point.payload.get("text", "") if point.payload else ""
                score = _keyword_score(query, text)
                if score > 0:
                    scored.append((point.id, score, point))

            if offset is None:
                break
    except Exception:
        return []

    scored.sort(key=lambda x: x[1], reverse=True)
    return scored[:limit]


def reciprocal_rank_fusion(
    vector_results: List[tuple],
    keyword_results: List[tuple],
    k: float = 60.0,
) -> List[tuple[Any, float]]:
    """
    Merge two ranked lists by Reciprocal Rank Fusion.

    Each result is identified by its id (first element of the tuple).
    Returns (id, fused_score) pairs ordered by RRF score, descending.
    """
    scores: dict = {}

    for rank, item in enumerate(vector_results):
        item_id = item[0]
        scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)

    for rank, item in enumerate(keyword_results):
        item_id = item[0]
        scores[item_id] = scores.get(item_id, 0.0) + 1.0 / (k + rank + 1)

    return sorted(scores.items(), key=lambda x: x[1], reverse=True)


def merge_hybrid_results(
    vector_points: List,
    keyword_ranked_ids: List[tuple],
    final_limit: int = 3,
) -> List:
    """
    Take Qdrant vector points and keyword results and return a fused,
    re-ranked list of points.

    Both input lists carry the underlying Qdrant record, so a document found
    only by the keyword pass survives fusion instead of being dropped.
    """
    vector_results = [(p.id, p) for p in vector_points]

    # Keyword hits win no priority: a document found by both passes should
    # resolve to the same record either way, so the vector point is kept.
    points_by_id = {item[0]: item[2] for item in keyword_ranked_ids if len(item) > 2}
    points_by_id.update({p.id: p for p in vector_points})

    fused = reciprocal_rank_fusion(vector_results, keyword_ranked_ids)

    merged = []
    for item_id, _score in fused:
        point = points_by_id.get(item_id)
        if point is not None:
            merged.append(point)
        if len(merged) >= final_limit:
            break
    return merged
