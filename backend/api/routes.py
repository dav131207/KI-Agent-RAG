"""API routes for Professor Pepe."""

import json
import random
from io import BytesIO
from pathlib import Path
from typing import Optional

import httpx
from fastapi import APIRouter, File, HTTPException, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from PIL import Image

from analytics import get_feedback_export, get_summary, track_event
from core.auth import check_admin_auth
from api.schemas import (
    ChatRequest,
    EmoteRequest,
    EventRequest,
    ImageRequest,
    IngestTextRequest,
    RarePepeRequest,
)
from core.config import IMAGE_API_BASE, LLM_PROVIDER, MEMES_DIR
from core.http import http
from core.providers import get_llm_provider
from services.chain_image_service import render_chain_stats_card
from services.chat_service import GET_COINS_TEXTS, generate_chat_response, is_social_command
from services.crypto_service import get_pepe_chain_data
from services.emote_service import emote_files, pick_emote
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
from services.rag_service import get_random_pepe_meme, search_context, search_pepe_memes
from rag import ingest_text

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
        "image_api": IMAGE_API_BASE,
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
    context = ""
    rag_chunk_count = 0
    if req.use_rag:
        chunks = search_context(req.message, limit=3)
        rag_chunk_count = len(chunks)
        if chunks:
            context = "\n\n---\n\n".join(chunks)

    track_event(
        client_ip=get_client_host(request),
        event_type="rag_retrieval",
        message=req.message,
        session_id=request.cookies.get("pepe_session"),
        metadata={"chunk_count": rag_chunk_count, "use_rag": req.use_rag},
    )

    target_language = await resolve_target_language(
        None, req.history, request, http
    )

    response = await generate_chat_response(
        req.topic,
        req.message,
        req.history,
        context,
        language=target_language,
        stream=req.stream,
        base_url=str(request.base_url),
    )

    if req.stream:
        return StreamingResponse(
            response,
            media_type="text/plain",
            headers={"X-RAG-Chunks": str(rag_chunk_count)},
        )
    return {"text": response, "rag_chunk_count": rag_chunk_count}


@router.post("/image")
async def fetch_image(req: ImageRequest, request: Request):
    """Fetch an image from the OnlyPepes API using keywords/tags."""
    pepe = await fetch_onlypepes_image(http, req.topic)
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


@router.post("/rare_pepe")
async def fetch_rare_pepe(req: RarePepeRequest, request: Request):
    """Return a non-politically-sensitive rare pepe from the Qdrant collection."""
    query = (req.query or "").strip().lower()
    no_context = not query or query == "rare pepe"
    target_language = await resolve_target_language(req.language, req.history, request, http)

    if no_context:
        pepe = get_random_pepe_meme()
    else:
        results = search_pepe_memes(req.query, limit=20)
        pepe = random.choice(results) if results else None

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
        "language": target_language,
    }


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
async def ingest_text_endpoint(req: IngestTextRequest):
    """Ingest plain text into the Qdrant knowledge base."""
    count = ingest_text(req.text)
    if count == 0:
        raise HTTPException(status_code=503, detail="Qdrant not configured")
    return {"ingested_chunks": count}


@router.post("/ingest/file")
async def ingest_file_endpoint(file: UploadFile = File(...)):
    """Upload and ingest a text/markdown file into Qdrant."""
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
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
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
        url = f"{request.base_url}memes/community/{filename}"
    else:
        url = f"{request.base_url}api/watermark?path=/memes/community/{filename}"

    return {"art": {"url": url, "description": art["description"], "label": art["label"]}}
