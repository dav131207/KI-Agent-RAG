"""API routes for Professor Pepe."""

import asyncio
import json
import logging
import os
import random
import time
from io import BytesIO
from pathlib import Path
from urllib.parse import quote
from typing import Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image

from analytics import (
    get_chunk_quality,
    get_eval_cases_from_feedback,
    get_feedback_export,
    get_feedback_reasons,
    get_knowledge_gaps,
    get_summary,
    track_event,
)
from core.auth import check_admin_auth
from api.schemas import (
    ChatRequest,
    EmoteRequest,
    EventRequest,
    ImageRequest,
    IngestTextRequest,
    RarePepeRequest,
)
from core.config import DEFAULT_MODEL, IMAGE_API_BASE, LLM_PROVIDER, MEMES_DIR, POST_MODEL
from rag.qdrant_store import EMBEDDING_MODEL
from core.http import http
from core.providers import get_llm_provider
from core.storage import storage_state
from services.chain_image_service import render_chain_stats_card
from services.chat_service import GET_COINS_TEXTS, generate_chat_response, is_social_command
from services.crypto_service import get_pepe_chain_data
from services.emote_service import emote_files, export_emote, pick_emote, suggest_emotes
from services.image_service import (
    ALLOWED_IMAGE_PREFIXES,
    apply_watermark,
    build_watermarked_url,
    extract_image_search_term,
    fetch_onlypepes_image,
    get_watermark,
    validate_memes_path,
)
from services.language_service import (
    detect_language_from_request,
    get_client_host,
    resolve_target_language,
    translate_text,
)
from services.rag_service import (
    get_random_pepe_meme,
    search_context_detailed,
    search_pepe_memes,
)
from rag import ingest_text

logger = logging.getLogger(__name__)

# How long an answer may wait for retrieved context before going without it.
RETRIEVAL_BUDGET_SECONDS = float(os.getenv("RETRIEVAL_BUDGET_SECONDS", "1.5"))

# Community art is user-submitted, so the size is somebody else's decision.
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "25")) * 1024 * 1024

router = APIRouter()


def _extract_pepe_image_url(pepe: dict) -> Optional[str]:
    """Find an image URL in the Qdrant payload, trying several common field names."""
    for key in ("url", "image_url", "image", "src", "link", "source", "permalink"):
        value = pepe.get(key)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return None


@router.get("/health")
async def health():
    return {
        "status": "ok",
        "llm_provider": LLM_PROVIDER,
        # render.yaml pins a different model than config.py defaults to, and
        # the environment wins — so report what is actually being called.
        "model": DEFAULT_MODEL,
        "post_model": POST_MODEL,
        "embedding_model": EMBEDDING_MODEL,
        "image_api": IMAGE_API_BASE,
        # Reports whether backend/data outlived the previous deploy. Compare
        # first_seen across redeploys: unchanged means the volume persists.
        "storage": storage_state(),
    }


@router.get("/language")
async def language(request: Request):
    """Return the detected language for the current client."""
    lang = await detect_language_from_request(request, http)
    return {"language": lang}


@router.post("/event")
async def record_event(req: EventRequest, request: Request):
    """Record an analytics event from the frontend."""
    country = request.headers.get("CF-IPCountry")
    language = await detect_language_from_request(request, http)
    track_event(
        client_ip=get_client_host(request),
        event_type=req.event_type,
        command=req.command,
        message=req.message,
        language=language,
        country=country,
        session_id=req.session_id,
        user_agent=req.user_agent or request.headers.get("User-Agent"),
        feedback=req.feedback,
        conversion_type=req.conversion_type,
        latency_ms=req.latency_ms,
        metadata=req.metadata,
        user_message=req.user_message,
        wallet_address=req.wallet_address,
    )
    return {"status": "ok"}


@router.post("/admin/verify-token")
async def verify_token(request: Request):
    """Verify if the provided token is valid."""
    auth_header = request.headers.get("Authorization")
    try:
        check_admin_auth(auth_header)
        return {"valid": True}
    except HTTPException:
        raise HTTPException(
            status_code=401,
            detail="Invalid token",
        )


@router.get("/analytics")
async def analytics_summary(request: Request, days: int = 7):
    """Return an aggregated analytics summary for the last N days."""
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)
    return get_summary(days=days)


@router.get("/analytics/learning")
async def analytics_learning(request: Request, days: int = 30):
    """
    Report what the feedback says about the knowledge base.

    Read-only on purpose: nothing here changes how answers are generated. The
    app is public, so ratings can be spammed, and feedback should inform a
    decision you make rather than silently steer the agent.
    """
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)
    return {
        "days": days,
        "knowledge_gaps": get_knowledge_gaps(days=days),
        "chunk_quality": get_chunk_quality(days=days),
        "feedback_reasons": get_feedback_reasons(days=days),
        "eval_cases_available": len(get_eval_cases_from_feedback(days=max(days, 90))),
    }


@router.get("/analytics/eval-cases")
async def analytics_eval_cases(request: Request, days: int = 90):
    """Export retrieval eval cases derived from thumbs-up answers."""
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)
    cases = get_eval_cases_from_feedback(days=days)
    return Response(
        content=json.dumps(cases, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": 'attachment; filename="eval_cases.json"'},
    )


@router.get("/analytics/export")
async def analytics_export(request: Request, days: int = 90, format: str = "json"):
    """Export feedback events (question + response + rating) for a RAG eval pipeline."""
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)

    records = get_feedback_export(days=days)

    if format == "jsonl":
        body = "\n".join(json.dumps(r, ensure_ascii=False) for r in records)
        return Response(
            content=body,
            media_type="application/x-ndjson",
            headers={"Content-Disposition": f'attachment; filename="feedback_{days}d.jsonl"'},
        )

    body = json.dumps(records, ensure_ascii=False, indent=2)
    return Response(
        content=body,
        media_type="application/json",
        headers={"Content-Disposition": f'attachment; filename="feedback_{days}d.json"'},
    )


@router.post("/chat")
async def chat(req: ChatRequest, request: Request):
    """Handle a chat message and stream or return the LLM response."""
    # Every phase is timed. Optimising this path from local measurements was
    # guesswork: what is slow depends on the distance to Gemini and Qdrant from
    # wherever this runs, which only the deployment can answer.
    timings: dict[str, int] = {}
    started = time.perf_counter()

    def mark(phase: str) -> None:
        elapsed = int((time.perf_counter() - started) * 1000)
        timings[phase] = elapsed - sum(timings.values())

    context = ""
    rag_chunk_count = 0
    chunk_ids: list[str] = []
    if req.use_rag:
        # Retrieval embeds the query and queries Qdrant, both blocking calls.
        # Run on a worker thread so they do not hold the loop while every other
        # request waits.
        # The embedding call is the slow, unpredictable half of retrieval:
        # measured at 450ms on one request and roughly 2.9s on another, for the
        # same work. Past the budget the answer goes ahead without retrieved
        # context — a slightly less informed reply beats a visibly stuck one.
        try:
            hits = await asyncio.wait_for(
                asyncio.to_thread(search_context_detailed, req.message, 3),
                timeout=RETRIEVAL_BUDGET_SECONDS,
            )
        except asyncio.TimeoutError:
            hits = []
            logger.warning(
                "Retrieval exceeded %.1fs; answering without context.",
                RETRIEVAL_BUDGET_SECONDS,
            )
        rag_chunk_count = len(hits)
        chunk_ids = [h["chunk_id"] for h in hits if h.get("chunk_id")]
        if hits:
            context = "\n\n---\n\n".join(h["text"] for h in hits)
    mark("retrieval")

    track_event(
        client_ip=get_client_host(request),
        event_type="rag_retrieval",
        message=req.message,
        session_id=request.cookies.get("pepe_session"),
        # chunk_ids let a later thumbs-down be traced back to its sources.
        metadata={
            "chunk_count": rag_chunk_count,
            "chunk_ids": chunk_ids,
            "use_rag": req.use_rag,
        },
    )

    mark("analytics")

    target_language = await resolve_target_language(
        None, req.history, request, http
    )
    mark("language")

    response = await generate_chat_response(
        req.topic,
        req.message,
        req.history,
        context,
        language=target_language,
        stream=req.stream,
        base_url=str(request.base_url),
    )
    mark("prepare")

    if req.stream:
        async def timed(stream):
            """Log how long the model took to produce its first chunk."""
            first = True
            async for chunk in stream:
                if first:
                    ttft = int((time.perf_counter() - started) * 1000)
                    logger.info(
                        "chat timing ms: %s, first_token_total=%s",
                        ", ".join(f"{k}={v}" for k, v in timings.items()),
                        ttft,
                    )
                    first = False
                yield chunk

        return StreamingResponse(
            timed(response),
            media_type="text/plain",
            headers={
                # Pre-generation phases; the model's own time is in the log,
                # since headers are sent before the first chunk exists.
                "X-Timing": ";".join(f"{k}={v}" for k, v in timings.items()),
                "X-RAG-Chunks": str(rag_chunk_count),
                # Echoed back so the client can attach them to a rating.
                "X-RAG-Chunk-Ids": ",".join(chunk_ids),
                "Access-Control-Expose-Headers": "X-RAG-Chunks, X-RAG-Chunk-Ids, X-Timing",
            },
        )
    return {
        "text": response,
        "rag_chunk_count": rag_chunk_count,
        "rag_chunk_ids": chunk_ids,
    }


@router.post("/image")
async def fetch_image(req: ImageRequest, request: Request):
    """Fetch an image from the OnlyPepes API using keywords/tags."""
    pepe = await fetch_onlypepes_image(http, req.topic, req.context)
    external_url = pepe.get("url")
    watermarked_url = build_watermarked_url(str(request.base_url), external_url, None)
    return {
        "url": watermarked_url,
        "description": pepe.get("description", ""),
        "tags": pepe.get("tags") or [],
    }


@router.post("/get_coins")
async def get_coins(request: Request):
    """Return a concise guide with faucet, wallet, Discord and tipping channel links."""
    language = await detect_language_from_request(request, http)
    text = GET_COINS_TEXTS.get(language)
    if text is None:
        text = GET_COINS_TEXTS["English"]
        if language and language.lower() not in ("english", "en"):
            text = await translate_text(text, language) or text
    return {"text": text}


@router.post("/emote")
async def fetch_emote(req: EmoteRequest):
    """Pick a context-aware local emote based on the provided text."""
    if not emote_files:
        raise HTTPException(status_code=404, detail="No emotes available")
    url = pick_emote(req.text)
    return {"url": url}


RARE_PEPE_POOL = 8


def _conversation_query(history: list[dict], max_turns: int = 4, max_chars: int = 600) -> str:
    """
    Build a search query from what the conversation has been about.

    The button sends the literal string "rare pepe", which carries no subject,
    so the collection was only ever sampled at random and its embeddings went
    unused. The recent turns are the subject the user is actually on.
    """
    parts = []
    for turn in reversed(history or []):
        text = (turn.get("text") or "").strip()
        # Skip the command echoes; they describe the button, not the topic.
        if not text or text.lower().startswith(("rare pepe", "random ", "create a social")):
            continue
        parts.append(text)
        if len(parts) >= max_turns:
            break

    return " ".join(reversed(parts))[:max_chars].strip()


@router.post("/rare_pepe")
async def fetch_rare_pepe(req: RarePepeRequest, request: Request):
    """Return a non-politically-sensitive rare pepe from the Qdrant collection."""
    query = (req.query or "").strip()
    generic = not query or query.lower() == "rare pepe"
    target_language = await resolve_target_language(req.language, req.history, request, http)

    # An explicit query wins; otherwise fall back to the conversation, and only
    # to a random draw when there is nothing to search on at all.
    search_query = query if not generic else _conversation_query(req.history)
    matched_on = "query" if not generic else ("conversation" if search_query else "random")

    pepe = None
    if search_query:
        results = search_pepe_memes(search_query, limit=RARE_PEPE_POOL)
        # Sampling the closest few rather than taking the single best keeps
        # repeated presses varied. The pool stays small on purpose: drawing
        # from a wide one dilutes the match back towards random.
        pepe = random.choice(results) if results else None
        if not pepe:
            matched_on = "random"

    if not pepe:
        pepe = get_random_pepe_meme()

    if not pepe:
        raise HTTPException(status_code=404, detail="No rare pepe found")

    filename = pepe.get("filename", "")
    file_path = pepe.get("file_path", "")
    if not filename and file_path:
        filename = Path(file_path).name

    external_url = _extract_pepe_image_url(pepe)
    url = build_watermarked_url(str(request.base_url), external_url, filename)

    description = pepe.get("description", "")
    explanation = pepe.get("explanation", "")

    if target_language and target_language.lower() not in ("english", "en"):
        description = await translate_text(description, target_language)
        explanation = await translate_text(explanation, target_language)

    return {
        "url": url,
        "filename": filename,
        "description": description,
        "explanation": explanation,
        # Says whether this was picked to fit the conversation or drawn blind,
        # so a mismatch can be told apart from a missed search.
        "matched_on": matched_on,
        "language": target_language,
    }


@router.get("/emotes/suggest")
async def suggest_emotes_endpoint(text: str = "", limit: int = 4, animated: bool = True):
    """
    Shortlist emotes matching a piece of text, for attaching to a social post.

    Returns candidates rather than one pick: an emote that misses the mood is
    worse under a post than none at all, so the choice stays with the author.
    """
    names = suggest_emotes(text, limit=max(1, min(limit, 12)), animated_only=animated)
    if not names:
        raise HTTPException(status_code=404, detail="No emotes available")
    return {
        "emotes": [
            {
                "name": name,
                # Small original for the picker, upscaled copy for downloading.
                "preview_url": f"/emotes/{quote(name)}",
                "download_url": f"/api/emotes/export?name={quote(name)}",
            }
            for name in names
        ]
    }


@router.get("/emotes/export")
async def export_emote_endpoint(name: str):
    """Serve an emote scaled up for social media, animation intact."""
    data, media_type = export_emote(name)
    extension = "gif" if media_type == "image/gif" else "png"
    stem = Path(name).stem
    return Response(
        content=data,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{stem}.{extension}"',
            "Cache-Control": "public, max-age=86400",
        },
    )


@router.get("/chain-stats")
async def chain_stats():
    """Return the live on-chain snapshot from the Pepeblocks explorer."""
    chain = await get_pepe_chain_data(http)
    if not chain:
        raise HTTPException(status_code=503, detail="Explorer unavailable")
    return chain


@router.get("/chain-stats.png")
async def chain_stats_image(metric: Optional[str] = None):
    """
    Render the live on-chain snapshot as a stat card image for social posts.

    `metric` picks the headline figure (hashrate, blocktime, difficulty,
    height, supply, peers) so repeated posts do not all lead with the same
    number. Unknown or unavailable metrics fall back to the next best one.
    """
    chain = await get_pepe_chain_data(http)
    png = render_chain_stats_card(chain, metric=metric)
    if png is None:
        raise HTTPException(status_code=503, detail="Explorer unavailable")
    return Response(
        content=png,
        media_type="image/png",
        # Matches the 60s explorer cache so shared posts stay reasonably fresh.
        headers={"Cache-Control": "public, max-age=60"},
    )


@router.get("/watermark")
async def watermark_proxy(url: Optional[str] = None, path: Optional[str] = None):
    """Fetch an external or local image, burn in the watermark and return it."""
    if not url and not path:
        raise HTTPException(status_code=400, detail="Provide url or path")

    watermark = get_watermark()
    if watermark is None:
        raise HTTPException(status_code=503, detail="Watermark not configured")

    if url:
        if not any(url.startswith(p) for p in ALLOWED_IMAGE_PREFIXES):
            raise HTTPException(status_code=400, detail="Image URL not allowed")
        try:
            r = await http.get(url)
            r.raise_for_status()
            data = r.content
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Image fetch error: {e}")
    else:
        file_path = validate_memes_path(path)
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        data = file_path.read_bytes()

    try:
        base = Image.open(BytesIO(data))
        result = apply_watermark(base)
        buf = BytesIO()
        result.save(buf, format="PNG")
        buf.seek(0)
        return StreamingResponse(buf, media_type="image/png")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Watermark error: {e}")


@router.post("/ingest/text")
async def ingest_text_endpoint(req: IngestTextRequest, request: Request):
    """
    Ingest plain text into the Qdrant knowledge base. Admin only.

    Whatever lands here is retrieved as context and presented to users as fact.
    On a public app that made the knowledge base writable by anyone — including
    with wallet addresses the agent would then repeat.
    """
    check_admin_auth(request.headers.get("Authorization"))
    count = ingest_text(req.text)
    if count == 0:
        raise HTTPException(status_code=503, detail="Qdrant not configured")
    return {"ingested_chunks": count}


@router.post("/ingest/file")
async def ingest_file_endpoint(request: Request, file: UploadFile = File(...)):
    """Upload and ingest a text/markdown file into Qdrant. Admin only."""
    check_admin_auth(request.headers.get("Authorization"))
    allowed = {".txt", ".md", ".markdown"}
    ext = Path(file.filename or "").suffix.lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"Only {allowed} files supported")

    content = await file.read()
    text = content.decode("utf-8", errors="ignore")
    count = ingest_text(text, source=file.filename)
    if count == 0:
        raise HTTPException(status_code=503, detail="Qdrant not configured")
    return {"ingested_chunks": count, "filename": file.filename}

from fastapi import Form
import shutil
import uuid
from api.schemas import ArtUpdateRequest

@router.post("/community-art/upload")
async def upload_community_art(label: str = Form(...), file: UploadFile = File(...)):
    """Upload community art, get description via Gemini, and store pending."""
    from services.art_service import add_art, UPLOADS_DIR
    
    ext = Path(file.filename or "").suffix.lower()
    if ext not in {".png", ".jpg", ".jpeg", ".gif", ".mp4", ".webm"}:
        raise HTTPException(status_code=400, detail="Unsupported file format")
    
    new_filename = f"{uuid.uuid4().hex}{ext}"
    file_path = UPLOADS_DIR / new_filename

    # Copied without a bound before, so one request could fill the volume — and
    # every upload costs a Gemini vision call. Written in chunks against a cap,
    # discarding the partial file if the cap is passed.
    written = 0
    try:
        with open(file_path, "wb") as buffer:
            while chunk := await file.read(1024 * 1024):
                written += len(chunk)
                if written > MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413,
                        detail=f"File exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB",
                    )
                buffer.write(chunk)
    except Exception:
        file_path.unlink(missing_ok=True)
        raise

    art = add_art(new_filename, label, file_path, file.content_type or "image/png")
    return {"status": "success", "art": art}

@router.get("/admin/community-art")
async def get_all_community_art(request: Request):
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)
    from services.art_service import get_all_art
    return {"art": get_all_art()}


@router.put("/admin/community-art/{art_id}")
async def update_community_art(art_id: int, req: ArtUpdateRequest, request: Request):
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)
    from services.art_service import update_art
    art = update_art(art_id, req.status, req.label)
    if not art:
        raise HTTPException(status_code=404, detail="Art not found")
    return {"art": art}

@router.delete("/admin/community-art/{art_id}")
async def delete_community_art(art_id: int, request: Request):
    auth_header = request.headers.get("Authorization")
    check_admin_auth(auth_header)
    from services.art_service import delete_art
    success = delete_art(art_id)
    if not success:
        raise HTTPException(status_code=404, detail="Art not found")
    return {"status": "deleted"}

@router.get("/community-art/labels")
async def get_community_art_labels():
    from services.art_service import get_labels
    return {"labels": get_labels()}

@router.get("/community-art/random")
async def get_random_community_art(label: str, request: Request):
    from services.art_service import get_random_art
    art = get_random_art(label)
    if not art:
        raise HTTPException(status_code=404, detail="No art found for this label")
    
    filename = str(art['filename'])
    if filename.lower().endswith(('.mp4', '.webm')):
        url = f"{request.base_url}community/{filename}"
    else:
        url = f"{request.base_url}api/watermark?path=/community/{filename}"

    return {"art": {"url": url, "description": art["description"], "label": art["label"]}}
