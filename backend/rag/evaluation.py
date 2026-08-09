"""
Simple RAG evaluation helpers.

Allows you to define a small set of labelled queries with the ids of the
chunks that should be retrieved. This makes it possible to measure whether
changes to chunking, embedding or retrieval actually improve results.
"""

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, List


@dataclass
class EvalCase:
    query: str
    relevant_chunk_ids: List[str]


def load_eval_cases(path: Path) -> List[EvalCase]:
    """Load evaluation cases from a JSON file."""
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [EvalCase(query=c["query"], relevant_chunk_ids=c["relevant_chunk_ids"]) for c in raw]


def precision_at_k(retrieved: List[str], relevant: List[str], k: int = 3) -> float:
    """Calculate Precision@K for a single query."""
    retrieved_k = retrieved[:k]
    if not retrieved_k:
        return 0.0
    hits = sum(1 for item in retrieved_k if item in relevant)
    return hits / len(retrieved_k)


def recall_at_k(retrieved: List[str], relevant: List[str], k: int = 3) -> float:
    """Calculate Recall@K for a single query."""
    if not relevant:
        return 0.0
    hits = sum(1 for item in retrieved[:k] if item in relevant)
    return hits / len(relevant)


def evaluate_retriever(
    cases: List[EvalCase],
    retrieve_fn: Callable[[str, int], List[str]],
    k: int = 3,
) -> dict:
    """
    Run a retriever against labelled cases and return aggregated metrics.

    retrieve_fn should accept (query, limit) and return a list of chunk ids.
    """
    precisions = []
    recalls = []
    skipped = 0

    for case in cases:
        # A case without labelled chunk ids can only ever score 0 and would
        # silently drag the averages down, so it is reported instead.
        if not case.relevant_chunk_ids:
            skipped += 1
            continue
        retrieved = retrieve_fn(case.query, k)
        precisions.append(precision_at_k(retrieved, case.relevant_chunk_ids, k))
        recalls.append(recall_at_k(retrieved, case.relevant_chunk_ids, k))

    return {
        "k": k,
        "num_cases": len(cases),
        "num_evaluated": len(precisions),
        "num_skipped_unlabelled": skipped,
        "precision_at_k": round(sum(precisions) / len(precisions), 3) if precisions else None,
        "recall_at_k": round(sum(recalls) / len(recalls), 3) if recalls else None,
    }
