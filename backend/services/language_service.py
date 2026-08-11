"""
Language detection and translation services.

Handles IP geolocation, Cloudflare country headers and LLM-based language
identification/translation.
"""

import asyncio
import re
from typing import Optional

import httpx
from fastapi import Request

from core.cache import cache
from core.config import DEFAULT_MODEL
from core.providers import get_llm_provider
from core.providers.base import LLMError

# One entry per client IP and nothing ever removed one, so this grew for the
# life of the process. Bounded with FIFO eviction: geolocation is a cheap
# lookup, so losing the oldest entries costs one extra request at worst.
_geo_cache: dict[str, str] = {}
GEO_CACHE_MAX = 5000


def _remember_geo(client_host: str, language: str) -> None:
    """Cache a lookup, evicting the oldest entry when full."""
    if len(_geo_cache) >= GEO_CACHE_MAX:
        _geo_cache.pop(next(iter(_geo_cache)), None)
    _geo_cache[client_host] = language

COUNTRY_TO_LANGUAGE = {
    "DE": "German",
    "AT": "German",
    "CH": "German",
    "US": "English",
    "GB": "English",
    "CA": "English",
    "AU": "English",
    "NZ": "English",
    "IE": "English",
    "FR": "French",
    "BE": "French",
    "ES": "Spanish",
    "MX": "Spanish",
    "IT": "Italian",
    "PT": "Portuguese",
    "BR": "Portuguese",
    "NL": "Dutch",
    "PL": "Polish",
    "RU": "Russian",
    "UA": "Ukrainian",
    "TR": "Turkish",
    "JP": "Japanese",
    "KR": "Korean",
    "CN": "Chinese",
    "TW": "Chinese",
    "HK": "Chinese",
    "IN": "Hindi",
    "BD": "Bengali",
    "PK": "Urdu",
    "LK": "Tamil",
    "NP": "English",
    "SE": "Swedish",
    "NO": "Norwegian",
    "DK": "Danish",
    "FI": "Finnish",
    "CZ": "Czech",
    "HU": "Hungarian",
    "RO": "Romanian",
    "GR": "Greek",
    "IL": "Hebrew",
    "SA": "Arabic",
    "AE": "Arabic",
    "EG": "Arabic",
    "ZA": "English",
    "SG": "English",
    "MY": "English",
    "PH": "English",
    "ID": "Indonesian",
    "TH": "Thai",
    "VN": "Vietnamese",
}


def get_client_host(request: Request) -> str:
    """Extract the real client IP from proxy headers when available."""
    cf_ip = request.headers.get("CF-Connecting-IP")
    if cf_ip:
        return cf_ip.strip()
    xff = request.headers.get("X-Forwarded-For")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


async def detect_language_from_ip(http_client: httpx.AsyncClient, client_host: str) -> str:
    """Detect the user's language from their IP address via ip-api.com."""
    if not client_host or client_host in ("127.0.0.1", "localhost", "::1"):
        return "English"

    if client_host in _geo_cache:
        return _geo_cache[client_host]

    try:
        response = await http_client.get(
            f"http://ip-api.com/json/{client_host}?fields=status,countryCode,message",
            timeout=5,
        )
        response.raise_for_status()
        data = response.json()
        if data.get("status") == "success":
            country = data.get("countryCode", "")
            language = COUNTRY_TO_LANGUAGE.get(country, "English")
            _remember_geo(client_host, language)
            return language
    except Exception:
        pass

    return "English"


async def detect_language_from_request(
    request: Request, http_client: httpx.AsyncClient
) -> str:
    """Detect language from Cloudflare country header or the client's IP."""
    cf_country = request.headers.get("CF-IPCountry")
    if cf_country:
        return COUNTRY_TO_LANGUAGE.get(cf_country.upper().strip(), "English")
    return await detect_language_from_ip(http_client, get_client_host(request))


# Scripts that identify a language on sight. Checked before any word lists,
# because a single character range settles it.
SCRIPT_RANGES = [
    ("Russian", (0x0400, 0x04FF)),
    ("Greek", (0x0370, 0x03FF)),
    ("Hebrew", (0x0590, 0x05FF)),
    ("Arabic", (0x0600, 0x06FF)),
    ("Hindi", (0x0900, 0x097F)),
    ("Bengali", (0x0980, 0x09FF)),
    ("Tamil", (0x0B80, 0x0BFF)),
    ("Telugu", (0x0C00, 0x0C7F)),
    ("Thai", (0x0E00, 0x0E7F)),
    ("Korean", (0xAC00, 0xD7AF)),
    ("Japanese", (0x3040, 0x30FF)),
    ("Chinese", (0x4E00, 0x9FFF)),
]

# Function words, which are the part of a sentence that stays constant.
STOPWORDS = {
    "German": {"der","die","das","und","ist","nicht","ich","du","wir","mit","auf","für","was","wie","aber","noch","schon","auch","sehr","kann","hat","wird","ein","eine","zu","von","im","bei"},
    "French": {"le","la","les","des","une","est","pas","je","tu","nous","vous","avec","pour","que","qui","mais","dans","sur","plus","très","être","fait","ça","cette"},
    "Spanish": {"el","los","las","una","es","no","yo","que","con","para","por","pero","como","más","muy","este","esta","son","tiene","hay","están"},
    "Italian": {"il","lo","gli","una","che","non","sono","con","per","ma","come","più","molto","questo","questa","hanno","essere","anche"},
    "Portuguese": {"os","as","uma","que","não","com","para","por","mas","como","mais","muito","este","esta","são","tem","você","isso"},
    "Dutch": {"de","het","een","en","is","niet","ik","wij","met","voor","maar","ook","heel","kan","heeft","wordt","deze","dat"},
    "Polish": {"nie","jest","się","tak","dla","ale","jak","bardzo","tego","tym","czy","już","tylko","może"},
    "Turkish": {"bir","ve","bu","için","ile","ama","çok","daha","olarak","var","yok","gibi","kadar"},
    "Indonesian": {"yang","dan","tidak","ini","itu","untuk","dengan","adalah","saya","kami","bisa","sudah","akan"},
    "Vietnamese": {"không","là","của","và","có","được","người","những","cho","với","này","một"},
}


def detect_language_heuristically(text: str) -> Optional[str]:
    """
    Identify a language without calling a model.

    The LLM detector cost a full round trip before every answer for anyone the
    geolocation reported as English. Scripts and function words settle almost
    every real message in microseconds; anything they cannot settle falls back
    to geolocation, which is a better trade than a second model call.
    """
    text = (text or "").strip()
    if len(text) < 3:
        return None

    for language, (low, high) in SCRIPT_RANGES:
        if sum(1 for ch in text if low <= ord(ch) <= high) >= 2:
            return language

    words = set(re.findall(r"[a-zà-öø-ÿğışçöüńłżźćęą]+", text.lower()))
    if not words:
        return None

    best, best_hits = None, 0
    for language, markers in STOPWORDS.items():
        hits = len(words & markers)
        if hits > best_hits:
            best, best_hits = language, hits

    # One shared word is chance; two is a signal.
    return best if best_hits >= 2 else None


async def detect_language_from_text(text: str) -> Optional[str]:
    """Ask the configured LLM to identify the language of the provided text."""
    cached = cache.get("detect_language_from_text", text)
    if cached:
        return cached

    provider = get_llm_provider()
    if not provider.is_configured:
        return None

    try:
        result = provider.generate(
            DEFAULT_MODEL,
            [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                'Identify the language of the following text. '
                                'Reply with only the English name of the language, e.g. "German", "English", "French".\n\n'
                                f'Text: "{text}"'
                            )
                        }
                    ],
                }
            ],
        )
        language = (result or "").strip().strip('"').strip("'")
        cache.set(language, "detect_language_from_text", text, ttl=86400)
        return language
    except LLMError:
        return None


async def translate_text(text: Optional[str], language: str) -> Optional[str]:
    """Translate text to the requested language using the configured LLM."""
    if not text:
        return text
    target = language.lower()
    if target in ("english", "en"):
        return text

    cached = cache.get("translate_text", text, language)
    if cached:
        return cached

    provider = get_llm_provider()
    if not provider.is_configured:
        return text

    try:
        # generate() is synchronous; awaiting it on a thread keeps a
        # translation from stalling every other request in flight.
        result = await asyncio.to_thread(
            provider.generate,
            DEFAULT_MODEL,
            [
                {
                    "role": "user",
                    "parts": [
                        {
                            "text": (
                                f'Translate the following text to {language}. '
                                'Preserve the meaning and tone. Reply with only the translation, no explanations.\n\n'
                                f'{text}'
                            )
                        }
                    ],
                }
            ],
        )
        translated = (result or "").strip()
        cache.set(translated or text, "translate_text", text, language, ttl=86400)
        return translated or text
    except LLMError:
        return text


async def resolve_target_language(
    language: Optional[str],
    history: list[dict],
    request: Request,
    http_client: httpx.AsyncClient,
) -> str:
    """Pick the target language: explicit > geolocation > last user message > English."""
    if language:
        return language

    geo_language = await detect_language_from_request(request, http_client)
    if geo_language and geo_language != "English":
        return geo_language

    # Geolocation said English, which is also what it returns when it knows
    # nothing. The last user message decides — by inspection, not by asking a
    # model, which used to add a full round trip ahead of every answer.
    for turn in reversed(history):
        if turn.get("role") == "user":
            text = turn.get("text", "")
            if text:
                detected = detect_language_heuristically(text)
                if detected:
                    return detected
                break

    return geo_language or "English"
