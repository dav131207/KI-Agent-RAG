"""
Qdrant-based RAG storage for Professor Pepe.

Embeddings are generated via the Gemini API (models/gemini-embedding-001
or models/text-embedding-004 with output_dimensionality=3072).
Supports both Qdrant Cloud and local Qdrant instances.
"""

import hashlib
import os
import random
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
from rag.retrieval import _keyword_search, merge_hybrid_results

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL = os.getenv("GEMINI_EMBEDDING_MODEL", "models/gemini-embedding-001")
QDRANT_URL = os.getenv("QDRANT_URL", "")
QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", "")
QDRANT_COLLECTION = os.getenv("QDRANT_COLLECTION", "professor_pepe")
PEPE_MEMES_COLLECTION = "pepe_memes"

VECTOR_SIZE = 3072  # dimension of models/gemini-embedding-001

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


def ensure_collection() -> bool:
    """Create the collection if it does not exist, and fix the vector size if needed."""
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

    existing_count = client.count(collection_name=QDRANT_COLLECTION).count
    points = [
        PointStruct(
            id=existing_count + i,
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
    return len(points)


def search_context(query: str, limit: int = 3, use_hybrid: bool = True) -> List[str]:
    """
    Search Qdrant for the most relevant chunks.

    When use_hybrid is True, dense vector search is combined with a simple
    keyword search over payloads and the results are fused with RRF.
    """
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

        if not use_hybrid:
            return [p.payload.get("text", "") for p in vector_points[:limit]]

        keyword_results = _keyword_search(
            client, QDRANT_COLLECTION, query, limit=limit * 4
        )
        fused = merge_hybrid_results(vector_points, keyword_results, final_limit=limit)
        return [p.payload.get("text", "") for p in fused if p.payload]
    except Exception:
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


def get_random_pepe_meme(max_attempts: int = 10) -> Optional[dict]:
    """Return a truly random, non-politically-sensitive pepe meme."""
    client = get_qdrant_client()
    if not client:
        return None

    try:
        total = client.count(collection_name=PEPE_MEMES_COLLECTION).count
        if total == 0:
            return None

        for _ in range(max_attempts):
            random_id = random.randint(0, total - 1)
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
