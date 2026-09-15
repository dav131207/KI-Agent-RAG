"""
Decide whether a chat message is asking for a picture, and what to search for.

The old gate was an English word list — show, image, picture, meme — which
"ich bin auf der Suche nach einem Pepe der gerade Fußball spielt" never
matched, and even when a request did match, the search term handed to the
index was the whole sentence in the user's language against captions
written in English. One small model call answers both questions at once.
"""

import asyncio
import json
import logging
import re
from typing import Optional

from core.config import DEFAULT_MODEL
from core.providers import get_llm_provider
from core.providers.base import LLMError

logger = logging.getLogger(__name__)

_PROMPT = """You read one message a user sent to Professor Pepe, a chat assistant for the
Pepecoin community that can look up pictures of Pepe the frog in an
English-captioned image index.

Decide whether the user is asking to SEE a picture (a Pepe, a meme, an image,
a drawing, a GIF), in any language. Asking what Pepecoin is, how mining works,
or for a social media post is NOT a picture request. Neither is a message
that merely mentions the word "pepe".

If it is a picture request, give the search term: one to three English words
naming the subject of the picture, the way a caption would — "football",
"pizza", "sleeping", "astronaut". Never include "pepe", "frog", "meme",
"image" or "picture" in it; every entry in the index is a Pepe already. If
the user just wants any picture with no subject, use an empty string.

Answer with JSON only, no code fence:
{{"wants_image": true or false, "search": "..."}}

Message:
{message}"""

_NOISE = {"pepe", "pepes", "frog", "frogs", "meme", "memes", "image", "picture", "pic"}


def _parse(text: str) -> Optional[dict]:
    """Locate the JSON object in the answer; None when there is none to trust."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        return None
    try:
        parsed = json.loads(match.group(0))
    except json.JSONDecodeError:
        return None
    if not isinstance(parsed, dict) or not isinstance(parsed.get("wants_image"), bool):
        return None

    search = str(parsed.get("search") or "").strip().strip('"').lower()
    # The prompt says so, and the model mostly obeys; the filter is for the
    # rest, because "football pepe" ranks every caption in the index equally.
    words = [w for w in re.findall(r"[a-z0-9'-]+", search) if w not in _NOISE]
    return {"wants_image": parsed["wants_image"], "search": " ".join(words[:3])}


async def detect_image_intent(message: str) -> dict:
    """
    Returns {"wants_image": bool, "search": str}.

    Defaults to no picture on any failure: a request that goes unanswered is
    still answered by the chat, while a false positive hangs four unrelated
    pictures under an answer about mining.
    """
    nothing = {"wants_image": False, "search": ""}
    message = (message or "").strip()
    if not message:
        return nothing

    provider = get_llm_provider()
    if not provider.is_configured:
        return nothing

    try:
        result = await asyncio.to_thread(
            provider.generate,
            DEFAULT_MODEL,
            [{"role": "user", "parts": [{"text": _PROMPT.format(message=message[:1000])}]}],
            temperature=0,
        )
    except LLMError as e:
        logger.warning("Image intent call failed: %s", e)
        return nothing

    return _parse(result or "") or nothing
