"""Shared async HTTP client."""

import httpx

http = httpx.AsyncClient(timeout=60, follow_redirects=True)


async def close_http() -> None:
    await http.aclose()
