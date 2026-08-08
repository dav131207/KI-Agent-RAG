"""
Language detection and translation services.

Handles IP geolocation, Cloudflare country headers and LLM-based language
identification/translation.
"""

from typing import Optional

import httpx
from fastapi import Request

from core.cache import cache
from core.config import DEFAULT_MODEL
from core.providers import get_llm_provider
from core.providers.base import LLMError

_geo_cache: dict[str, str] = {}

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
            _geo_cache[client_host] = language
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
        result = provider.generate(
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

    for turn in reversed(history):
        if turn.get("role") == "user":
            text = turn.get("text", "")
            if text:
                detected = await detect_language_from_text(text)
                if detected:
                    return detected
                break

    return geo_language or "English"
