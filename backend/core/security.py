"""
Security utilities: IP extraction and rate limiting.
"""

import time
from typing import Any

from fastapi import Request
from fastapi.responses import JSONResponse

from services.language_service import get_client_host

# Keyed by "<ip>:<path>". Every new visitor adds a key and nothing removed one,
# so the store grew for the lifetime of the process; entries are swept once
# their window has passed.
_rate_limit_store: dict[str, list[float]] = {}
_last_sweep = 0.0
SWEEP_INTERVAL_SECONDS = 300

RATE_LIMITS = {
    "/api/chat": (30, 60),
    "/api/rare_pepe": (20, 60),
    "/api/image": (30, 60),
    "/api/get_coins": (20, 60),
    "/api/emote": (60, 60),
    "/api/emotes/suggest": (60, 60),
    "/api/emotes/export": (60, 60),
    "/api/event": (120, 60),
    "/api/analytics": (60, 60),
    "/api/analytics/learning": (60, 60),
    "/api/analytics/eval-cases": (20, 60),
    "/api/watermark": (100, 60),
    "/api/chain-stats": (60, 60),
    "/api/chain-stats.png": (100, 60),
    "/api/community-art/upload": (5, 60),
    "/api/community-art/suggest": (60, 60),
    "/api/ingest/text": (10, 60),
    "/api/ingest/file": (10, 60),
}

RATE_LIMIT_EXEMPT = {"/api/health", "/api/language"}


def _rate_limit_key(request: Request) -> str:
    """Build a rate-limit key from the real client IP and the request path."""
    ip = get_client_host(request)
    return f"{ip}:{request.url.path}"


def _sweep_expired(now: float, window_seconds: int) -> None:
    """Drop keys whose whole window has passed, at most every few minutes."""
    global _last_sweep
    if now - _last_sweep < SWEEP_INTERVAL_SECONDS:
        return
    _last_sweep = now
    cutoff = now - window_seconds
    for key in [k for k, ts in _rate_limit_store.items() if not ts or ts[-1] <= cutoff]:
        del _rate_limit_store[key]


def is_rate_limited(request: Request) -> tuple[bool, dict[str, Any]]:
    """Check whether the current request exceeds its per-IP rate limit."""
    path = request.url.path
    if not path.startswith("/api") or path in RATE_LIMIT_EXEMPT:
        return False, {}

    limit_config = RATE_LIMITS.get(path, (30, 60))
    max_requests, window_seconds = limit_config
    key = _rate_limit_key(request)
    now = time.time()
    window_start = now - window_seconds

    _sweep_expired(now, window_seconds)

    timestamps = _rate_limit_store.get(key, [])
    timestamps = [ts for ts in timestamps if ts > window_start]
    timestamps.append(now)
    _rate_limit_store[key] = timestamps

    if len(timestamps) > max_requests:
        retry_after = int(window_seconds - (now - timestamps[0]))
        return True, {
            "retry_after": max(1, retry_after),
            "limit": max_requests,
            "window": window_seconds,
        }

    return False, {}


def rate_limit_response(details: dict[str, Any]) -> JSONResponse:
    """Build a 429 response for rate-limited requests."""
    return JSONResponse(
        status_code=429,
        content={
            "detail": "Rate limit exceeded. Please slow down.",
            "retry_after": details["retry_after"],
        },
        headers={"Retry-After": str(details["retry_after"])},
    )
