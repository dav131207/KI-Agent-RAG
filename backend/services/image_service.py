"""Image fetching, watermarking and proxying services."""

import os
from io import BytesIO
from pathlib import Path
from typing import Optional
from urllib.parse import quote

import httpx
from fastapi import HTTPException
from PIL import Image
from PIL.Image import Resampling

from core.config import COMMUNITY_ART_DIR, IMAGE_API_BASE, MEMES_DIR, WATERMARK_PATH

_watermark_image: Optional[Image.Image] = None


def get_watermark() -> Optional[Image.Image]:
    """Lazy-load the watermark image."""
    global _watermark_image
    if _watermark_image is None and os.path.exists(WATERMARK_PATH):
        _watermark_image = Image.open(WATERMARK_PATH).convert("RGBA")
    return _watermark_image


def apply_watermark(base_image: Image.Image) -> Image.Image:
    """Composite the watermark onto the bottom-right corner of an image."""
    watermark = get_watermark()
    if watermark is None:
        return base_image

    base = base_image.convert("RGBA")
    mark = watermark.copy()

    base_w, base_h = base.size
    mark_w = max(1, int(base_h * 0.20))
    mark_h = max(1, int(mark.height * mark_w / mark.width))
    mark = mark.resize((mark_w, mark_h), Resampling.LANCZOS)

    alpha = mark.getchannel("A").point(lambda p: int(p * 0.75))
    mark.putalpha(alpha)

    margin = int(base_h * 0.02)
    x = base_w - mark_w - margin
    y = base_h - mark_h - margin

    layer = Image.new("RGBA", base.size, (0, 0, 0, 0))
    layer.paste(mark, (x, y), mark)
    return Image.alpha_composite(base, layer)


def extract_image_search_term(topic: Optional[str]) -> str:
    """Strip command prefixes and polite wrappers so only keywords remain."""
    import re

    topic = (topic or "").strip()

    # A social-post command carries its subject in "Topic:", after several
    # other fields. Stripping only the leading verb left the whole parameter
    # list as the query — "Platform: Twitter. Language: English. Goal: ..." —
    # which matches nothing in the image index.
    structured = re.search(r"\bTopic:\s*(.+)$", topic, re.IGNORECASE | re.DOTALL)
    if structured:
        return structured.group(1).strip().rstrip(".").strip()

    topic = re.sub(
        r"^create\s+(a\s+)?social\s+media\s+post(\s+about\s+)?",
        "",
        topic,
        flags=re.IGNORECASE,
    ).strip()

    wrappers = [
        r"show\s+me\s+(a\s+|an\s+)?",
        r"send\s+me\s+(a\s+|an\s+)?",
        r"give\s+me\s+(a\s+|an\s+)?",
        r"image\s+of\s+(a\s+|an\s+)?",
        r"picture\s+of\s+(a\s+|an\s+)?",
        r"pic\s+of\s+(a\s+|an\s+)?",
        r"photo\s+of\s+(a\s+|an\s+)?",
        r"visual\s+of\s+(a\s+|an\s+)?",
        r"draw\s+(a\s+|an\s+)?",
    ]
    for pattern in wrappers:
        topic = re.sub(rf"^{pattern}", "", topic, flags=re.IGNORECASE).strip()

    return topic



def _relevance(query: str, item: dict) -> int:
    """Score a candidate by whole-word overlap with the query.

    Whole words on purpose: the index's substring matching is what returns
    "mine's" for "mining", and that is exactly what needs demoting.
    """
    import re

    words = {w for w in re.findall(r"[a-z]{3,}", (query or "").lower())}
    if not words:
        return 0

    haystack = " ".join(
        [
            str(item.get("description") or ""),
            " ".join(item.get("tags") or []),
        ]
    ).lower()
    present = set(re.findall(r"[a-z]{3,}", haystack))
    return len(words & present)


async def fetch_onlypepes_image(
    http_client: httpx.AsyncClient, topic: Optional[str], context: Optional[str] = None
) -> dict:
    """
    Fetch a Pepe image from the OnlyPepes API.

    `topic` is the search query — narrow, so the index returns candidates at
    all. `context` is what they are ranked against, and should be the finished
    post: a one-word topic scores every candidate identically, while the post
    text has enough words to tell them apart.
    """
    topic = extract_image_search_term(topic)
    is_pure_random = not topic or topic.lower() in {"random meme", "random pepe", "random"}

    # random=true is applied on top of the search rather than instead of it,
    # and it shuffles the matches far enough that the relevant ones drop out —
    # measured: 1 of 5 results mentioned the search term without it, 0 of 5
    # with it. Randomise only when there is nothing to match against.
    params: dict = {"limit": 1 if is_pure_random else 10}
    if is_pure_random:
        params["random"] = "true"
    else:
        params["search"] = topic

    async def _query(query_params: dict) -> list:
        try:
            r = await http_client.get(f"{IMAGE_API_BASE}/api/pepe", params=query_params)
            r.raise_for_status()
        except httpx.HTTPError as e:
            raise HTTPException(status_code=502, detail=f"Image API error: {e}")

        data = r.json().get("data")
        if isinstance(data, dict):
            return [data]
        return data if isinstance(data, list) else []

    candidates = await _query(params)

    # The index matches substrings, so a search for "mining" happily returns a
    # picture captioned "well mine's better". Asking for several and ranking
    # them here on whole-word overlap puts an actually relevant one first.
    if candidates and not is_pure_random:
        candidates.sort(key=lambda item: _relevance(context or topic, item), reverse=True)

    # A precise topic can legitimately match nothing. Falling back to a random
    # image keeps a post illustrated instead of failing the whole request.
    if not candidates and not is_pure_random:
        candidates = await _query({"limit": 1, "random": "true"})

    if not candidates:
        raise HTTPException(status_code=404, detail="No image found")

    return candidates[0]


def build_watermarked_url(base_url: str, external_url: Optional[str], filename: Optional[str]) -> Optional[str]:
    """Build a watermarked image URL for an external or local image."""
    if external_url:
        return f"{base_url}api/watermark?url={quote(external_url, safe='')}"
    if filename and MEMES_DIR and MEMES_DIR.is_dir():
        return f"{base_url}api/watermark?path=/memes/{quote(filename, safe='')}"
    return None


ALLOWED_IMAGE_PREFIXES = (
    IMAGE_API_BASE,
    "https://onlypepes.com",
    "https://archive.org",
    "https://i.imgur.com",
    "https://imgur.com",
    "https://i.redd.it",
    "https://pbs.twimg.com",
    "https://cdn.discordapp.com",
    "https://media.discordapp.net",
    "https://rarepepedirectory.com",
    "https://www.rarepepedirectory.com",
)


def is_image_url_allowed(url: str) -> bool:
    """Check whether an external image URL is allowed to be proxied."""
    return any(url.startswith(p) for p in ALLOWED_IMAGE_PREFIXES)


def _resolve_under(root: Optional[Path], relative: str, missing_detail: str) -> Path:
    """Resolve `relative` under `root`, refusing anything that escapes it."""
    if not root or not root.is_dir():
        raise HTTPException(status_code=503, detail=missing_detail)
    file_path = (root / relative).resolve()
    root_resolved = root.resolve()
    if root_resolved not in file_path.parents and file_path != root_resolved:
        raise HTTPException(status_code=400, detail="Invalid image path")
    return file_path


def validate_memes_path(path: str) -> Path:
    """
    Resolve a local image path and prevent directory traversal.

    Community art lives on the persistent volume rather than under MEMES_DIR,
    so it has its own prefix.
    """
    if path.startswith("/community/"):
        return _resolve_under(
            COMMUNITY_ART_DIR,
            path[len("/community/"):],
            "Community art directory not available",
        )
    if path.startswith("/memes/"):
        return _resolve_under(
            MEMES_DIR, path[len("/memes/"):], "Local memes directory not configured"
        )
    raise HTTPException(status_code=400, detail="Invalid image path")
