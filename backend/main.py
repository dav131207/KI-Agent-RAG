"""
Professor Pepe — FastAPI backend.

This file only wires the application together. Business logic lives in
services/, API routes in api/routes.py and shared utilities in core/.
"""

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from analytics import track_event
from api.routes import router
from core.config import MEMES_DIR
from core.http import close_http
from core.security import is_rate_limited, rate_limit_response
from services.language_service import get_client_host

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await close_http()


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
