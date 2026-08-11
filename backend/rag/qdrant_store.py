"""
Qdrant-based RAG storage for Professor Pepe.

Embeddings are generated via the Gemini API (models/gemini-embedding-001
or models/text-embedding-004 with output_dimensionality=3072).
Supports both Qdrant Cloud and local Qdrant instances.
"""

import hashlib
import logging
import os
import random
import time
import uuid
from pathlib import Path
from typing import List, Optional

from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PayloadSchemaType,
    PointStruct,
    VectorParams,
)

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None

from rag.chunking import semantic_chunk_text
from rag.retrieval import merge_hybrid_results, score_points_by_keyword

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "professor_pepe")
PEPE_MEMES_COLLECTION = "pepe_memes"

VECTOR_SIZE = 3072  # dimension of models/gemini-embedding-001

logger = logging.getLogger(__name__)

_embedding_client: Optional[genai.Client] = None  # type: ignore[valid-type]
_qdrant_client: Optional[QdrantClient] = None


def _get_embedding_client() -> Optional[genai.Client]:  # type: ignore[valid-type]
    """Return a Gemini client for embeddings, or None if not configured."""
    global _embedding_client
    if _embedding_client is None and genai and GEMINI_API_KEY:
        _embedding_client = genai.Client(api_key=GEMINI_API_KEY)
    return _embedding_client


def _embed(texts: List[str]) -> Optional[List[List[float]]]:
    """Embed a list of texts using the Gemini embedding API."""
    client = _get_embedding_client()
    if not client:
        return None

    try:
        config = None
        if types and "embedding-004" in EMBEDDING_MODEL:
            config = types.EmbedContentConfig(output_dimensionality=VECTOR_SIZE)
        response = client.models.embed_content(
            model=EMBEDDING_MODEL,
            contents=texts,
            config=config,
        )
        return [embedding.values for embedding in response.embeddings]
    except Exception:
        return None


def get_qdrant_client() -> Optional[QdrantClient]:
    """Return a configured Qdrant client, or None if not configured."""
    global _qdrant_client
    if _qdrant_client is not None:
        return _qdrant_client

    if QDRANT_URL:
        if QDRANT_URL == ":memory:":
            # In-memory Qdrant for local testing and CI.
            _qdrant_client = QdrantClient(":memory:")
        elif QDRANT_URL.startswith(("http://", "https://")):
            _qdrant_client = QdrantClient(
                url=QDRANT_URL,
                api_key=QDRANT_API_KEY or None,
                check_compatibility=False,
            )
        else:
            # Treat anything else as a local persistent path.
            path = Path(QDRANT_URL).expanduser()
            path.parent.mkdir(parents=True, exist_ok=True)
            _qdrant_client = QdrantClient(path=str(path))
    else:
        # Try a local Qdrant instance on the default port.
        try:
            _qdrant_client = QdrantClient(host="localhost", port=6333, check_compatibility=False)
            _qdrant_client.get_collections()
        except Exception:
            _qdrant_client = None

    return _qdrant_client


# Collections already verified in this process. The check costs two round trips
# — list the collections, then read one — and it ran on every message. Against a
# cluster on another continent that was roughly 300ms per answer spent
# confirming something that changes only when someone changes it.
_verified_collections: set[str] = set()


def forget_verified_collections() -> None:
    """Force the next call to re-check, after a query failed unexpectedly."""
    _verified_collections.clear()


def ensure_collection() -> bool:
    """Create the collection if it does not exist, and fix the vector size if needed."""
    if QDRANT_COLLECTION in _verified_collections:
        return True

    client = get_qdrant_client()
    if not client:
        return False

    try:
        collections = client.get_collections().collections
        names = {c.name for c in collections}
        if QDRANT_COLLECTION not in names:
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
            _verified_collections.add(QDRANT_COLLECTION)
            return True

        # If the collection exists with the wrong vector size, recreate it.
        info = client.get_collection(collection_name=QDRANT_COLLECTION)
        current_size = info.config.params.vectors.size
        if current_size != VECTOR_SIZE:
            client.delete_collection(collection_name=QDRANT_COLLECTION)
            client.create_collection(
                collection_name=QDRANT_COLLECTION,
                vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
            )
        _verified_collections.add(QDRANT_COLLECTION)
        return True
    except Exception:
        return False


def ensure_pepe_memes_collection(recreate: bool = False) -> bool:
    """Create the `pepe_memes` collection and index required payload fields."""
    client = get_qdrant_client()
    if not client:
        return False

    try:
        collections = {c.name for c in client.get_collections().collections}
        if PEPE_MEMES_COLLECTION in collections:
            if recreate:
                client.delete_collection(collection_name=PEPE_MEMES_COLLECTION)
                print(f"🗑️  Recreated collection: {PEPE_MEMES_COLLECTION}")
            else:
                return True

        client.create_collection(
            collection_name=PEPE_MEMES_COLLECTION,
            vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
        )

        # Index required for the political-sensitivity filter used in searches.
        client.create_payload_index(
            collection_name=PEPE_MEMES_COLLECTION,
            field_name="is_politically_sensitive",
            field_schema=PayloadSchemaType.BOOL,
        )
        return True
    except Exception as exc:
        print(f"❌ Could not ensure collection: {exc}")
        return False


def _chunk_id(text: str, source: str) -> str:
    """Create a stable, deterministic chunk identifier."""
    return hashlib.sha256(f"{source}:{text}".encode("utf-8")).hexdigest()[:16]


def _point_id(text: str, source: str) -> str:
    """
    Derive a deterministic Qdrant point id from the chunk content.

    Qdrant only accepts unsigned integers or UUIDs as ids, so the content hash
    is folded into a UUID. Re-ingesting the same source overwrites the existing
    points instead of appending duplicates.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source}:{text}"))


def ingest_text(text: str, source: str = "manual", chunk_size: int = 500, chunk_overlap: int = 50) -> int:
    """Split text into semantic chunks, embed them and store in Qdrant."""
    client = get_qdrant_client()
    if not client or not ensure_collection():
        return 0

    chunks = semantic_chunk_text(text, max_chunk_size=chunk_size, chunk_overlap=chunk_overlap)
    if not chunks:
        return 0

    embeddings = _embed(chunks)
    if embeddings is None:
        return 0

    points = [
        PointStruct(
            id=_point_id(chunks[i], source),
            vector=embeddings[i],
            payload={
                "text": chunks[i],
                "source": source,
                "chunk_id": _chunk_id(chunks[i], source),
            },
        )
        for i in range(len(chunks))
    ]

    client.upsert(collection_name=QDRANT_COLLECTION, points=points)
    # The collection has content again, so retrieval must stop skipping.
    set_knowledge_empty(False)
    return len(points)


# Set once the knowledge collection is known to be empty, so retrieval can be
# skipped entirely. An empty collection still costs an embedding call and a
# query — measured at ~1s per message against a cluster on another continent —
# and returns nothing either way.
_knowledge_is_empty = False
_empty_notice_logged = False


def set_knowledge_empty(is_empty: bool) -> None:
    """Record whether the knowledge collection has anything in it."""
    global _knowledge_is_empty, _empty_notice_logged
    _knowledge_is_empty = is_empty
    if not is_empty:
        _empty_notice_logged = False


def search_context(query: str, limit: int = 3, use_hybrid: bool = True) -> List[str]:
    """Return only the chunk texts. See search_context_detailed for the rest."""
    return [hit["text"] for hit in search_context_detailed(query, limit, use_hybrid)]


def search_context_detailed(
    query: str, limit: int = 3, use_hybrid: bool = True
) -> List[dict]:
    """
    Search Qdrant and return each hit with its identity.

    The chunk_id travels with the text so a later thumbs-down can be attributed
    to the sources that produced the answer — counting hits alone cannot say
    which chunk was responsible.

    When use_hybrid is True, dense vector search is combined with a simple
    keyword search over payloads and the results are fused with RRF.
    """
    global _empty_notice_logged
    if _knowledge_is_empty:
        # Nothing to find. Skipping saves the embedding call and the query,
        # which is the whole cost of retrieval when the collection is empty.
        if not _empty_notice_logged:
            logger.warning(
                "Skipping retrieval: knowledge collection %r is empty.",
                QDRANT_COLLECTION,
            )
            _empty_notice_logged = True
        return []

    client = get_qdrant_client()
    if not client or not ensure_collection():
        return []

    try:
        embeddings = _embed([query])
        if embeddings is None:
            return []
        embedding = embeddings[0]

        vector_response = client.query_points(
            collection_name=QDRANT_COLLECTION,
            query=embedding,
            limit=limit * 4 if use_hybrid else limit,
            with_payload=True,
        )
        vector_points = [r for r in vector_response.points if r.payload]

        if use_hybrid:
            # Rerank the candidates the vector pass already fetched rather than
            # scanning the collection: the extra round trips cost more than the
            # recall they bought.
            keyword_results = score_points_by_keyword(query, vector_points)
            hits = merge_hybrid_results(vector_points, keyword_results, final_limit=limit)
        else:
            hits = vector_points[:limit]

        return [
            {
                "chunk_id": p.payload.get("chunk_id") or str(p.id),
                "text": p.payload.get("text", ""),
                "source": p.payload.get("source", ""),
            }
            for p in hits
            if p.payload
        ]
    except Exception:
        forget_verified_collections()
        return []


def search_pepe_memes(query: str, limit: int = 10) -> List[dict]:
    """Search the pepe_memes collection, excluding politically sensitive entries."""
    client = get_qdrant_client()
    if not client:
        return []

    try:
        embeddings = _embed([query])
        if embeddings is None:
            return []
        embedding = embeddings[0]
        response = client.query_points(
            collection_name=PEPE_MEMES_COLLECTION,
            query=embedding,
            limit=limit,
            with_payload=True,
            query_filter=Filter(
                must=[
                    FieldCondition(
                        key="is_politically_sensitive",
                        match=MatchValue(value=False),
                    )
                ]
            ),
        )
        return [r.payload for r in response.points if r.payload]
    except Exception:
        return []


_pepe_meme_ids: list = []
_pepe_meme_ids_at: float = 0.0
PEPE_ID_CACHE_TTL = 600
PEPE_ID_CACHE_MAX = 20000


def _get_pepe_meme_ids(client: QdrantClient) -> list:
    """
    Return the real point ids, cached for a few minutes.

    Guessing ids from the point count assumed they run 0..count-1. The
    collection is uploaded with ids starting at 1, so id 0 never existed and the
    highest id was unreachable — and any collection using UUIDs missed entirely.
    Reading the ids costs one scroll per cache period and is exact.
    """
    global _pepe_meme_ids, _pepe_meme_ids_at
    now = time.time()
    if _pepe_meme_ids and now - _pepe_meme_ids_at < PEPE_ID_CACHE_TTL:
        return _pepe_meme_ids

    ids, offset = [], None
    while len(ids) < PEPE_ID_CACHE_MAX:
        points, offset = client.scroll(
            collection_name=PEPE_MEMES_COLLECTION,
            limit=1000,
            offset=offset,
            with_payload=False,
            with_vectors=False,
        )
        if not points:
            break
        ids.extend(p.id for p in points)
        if offset is None:
            break

    _pepe_meme_ids, _pepe_meme_ids_at = ids, now
    return ids


def get_random_pepe_meme(max_attempts: int = 10) -> Optional[dict]:
    """Return a truly random, non-politically-sensitive pepe meme."""
    client = get_qdrant_client()
    if not client:
        return None

    try:
        ids = _get_pepe_meme_ids(client)
        if not ids:
            return None

        for random_id in random.sample(ids, min(max_attempts, len(ids))):
            records = client.retrieve(
                collection_name=PEPE_MEMES_COLLECTION,
                ids=[random_id],
                with_payload=True,
            )
            for record in records:
                payload = record.payload
                if payload and payload.get("is_politically_sensitive") is False:
                    return payload
    except Exception:
        pass

    return None


def ingest_file(path: Path) -> int:
    """Read a plain text/markdown file and ingest it."""
    text = path.read_text(encoding="utf-8", errors="ignore")
    return ingest_text(text, source=str(path))


def describe_collections() -> dict:
    """
    Report what the configured collections actually hold.

    A wrong QDRANT_COLLECTION is invisible at runtime: retrieval simply finds
    nothing, the agent answers without knowledge, and the embedding call is
    still paid for on every message. Naming the collections and their sizes at
    startup turns a silent misconfiguration into a line in the log.
    """
    client = get_qdrant_client()
    if not client:
        return {"error": "Qdrant not configured"}

    try:
        available = sorted(c.name for c in client.get_collections().collections)
    except Exception as exc:
        return {"error": f"Qdrant unreachable: {exc}"}

    report: dict = {"available": available}
    for label, name in (
        ("knowledge", QDRANT_COLLECTION),
        ("memes", PEPE_MEMES_COLLECTION),
    ):
        if name not in available:
            report[label] = {"name": name, "exists": False, "points": 0}
            continue
        try:
            report[label] = {
                "name": name,
                "exists": True,
                "points": client.count(collection_name=name).count,
            }
        except Exception as exc:
            report[label] = {"name": name, "exists": True, "error": str(exc)}
    return report
