"""
Professor Pepe — FastAPI backend.

This file only wires the application together. Business logic lives in
services/, API routes in api/routes.py and shared utilities in core/.
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from analytics import track_event
from api.routes import router
from core.config import COMMUNITY_ART_DIR, MEMES_DIR
from core.http import close_http, http
from services.crypto_service import get_pepe_market_data
from core.security import is_rate_limited, rate_limit_response
from core.storage import record_boot
from services.language_service import get_client_host

# Nothing configured logging, so the root logger stayed at WARNING and every
# logger.info in the app was discarded — including the request timings, which
# is why they never reached the deployment's logs. uvicorn configures only its
# own loggers, not the application's.
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(levelname)s: %(name)s: %(message)s",
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Records whether the data directory survived the previous deploy.
    record_boot()
    # Warm the market cache so the first visitor does not pay for the fetch.
    # Detached: a slow or blocked explorer must not delay the server starting.
    warm = asyncio.create_task(_warm_caches())
    yield
    warm.cancel()
    await close_http()


async def _warm_caches() -> None:
    try:
        await get_pepe_market_data(http)
    except Exception as e:  # never let warming break startup
        logger.warning("Cache warm-up failed: %s", e)


app = FastAPI(title="Professor Pepe", version="1.0.0", lifespan=lifespan)


@app.middleware("http")
async def rate_limit_middleware(request, call_next):
    """Reject requests that exceed per-IP rate limits."""
    limited, details = is_rate_limited(request)
    if limited:
        return rate_limit_response(details)
    return await call_next(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(HTTPException)
async def track_http_errors(request: Request, exc: HTTPException):
    """Log every 4xx/5xx so failure modes show up in the analytics dashboard."""
    track_event(
        client_ip=get_client_host(request),
        event_type="error",
        command=request.url.path,
        message=str(exc.detail)[:300],
        session_id=request.cookies.get("pepe_session"),
        metadata={"status_code": exc.status_code},
    )
    return await http_exception_handler(request, exc)


@app.exception_handler(Exception)
async def track_unhandled_errors(request: Request, exc: Exception):
    """Catch anything unexpected so a bug doesn't fail silently in production."""
    track_event(
        client_ip=get_client_host(request),
        event_type="error",
        command=request.url.path,
        message=str(exc)[:300],
        session_id=request.cookies.get("pepe_session"),
        metadata={"status_code": 500, "type": type(exc).__name__},
    )
    logger.exception("Unhandled exception on %s", request.url.path)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


app.include_router(router, prefix="/api")

from fastapi.responses import FileResponse

if MEMES_DIR and MEMES_DIR.is_dir():
    app.mount("/memes", StaticFiles(directory=str(MEMES_DIR)), name="memes")

uploads_dir = Path(__file__).resolve().parent / "data" / "uploads"
if uploads_dir.is_dir():
    app.mount("/data/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

# Approved community art. Videos are served directly from here; images go
# through /api/watermark, which resolves the same directory.
COMMUNITY_ART_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/community", StaticFiles(directory=str(COMMUNITY_ART_DIR)), name="community")

frontend_dist = Path(__file__).resolve().parent.parent / "frontend" / "dist"
index_html = frontend_dist / "index.html"

@app.get("/{path:path}")
async def spa_fallback(path: str):
    """Serve static files or index.html for SPA routing."""
    if path.startswith("api/"):
        # Unmatched API routes must 404, not fall through to the SPA shell.
        return JSONResponse(status_code=404, content={"detail": "Not Found"})

    file_path = (frontend_dist / path).resolve()
    if frontend_dist.resolve() in file_path.parents or file_path == frontend_dist.resolve():
        if file_path.is_file():
            return FileResponse(file_path)

    return FileResponse(index_html)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
