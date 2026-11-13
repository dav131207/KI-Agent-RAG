"""One place where the Google GenAI client is built.

google-genai changed its default API version from v1beta to v1 in a later
major release, and requirements.txt only asks for >=1.0.0. The first image
built after that release therefore talked to v1, where the ``-latest`` model
aliases this project relies on do not exist: every chat answered with
404 NOT_FOUND for models/gemini-flash-lite-latest while the same key and the
same model worked fine on v1beta. The version the model ids were chosen
against is named here rather than inherited from whichever SDK release pip
happens to resolve at build time.
"""

import logging
from typing import Any, Optional

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover - the SDK is optional at import time
    genai = None
    types = None

logger = logging.getLogger(__name__)

# v1beta serves the *-latest aliases, the chat and post models and the
# embedding model. v1 serves everything except the aliases.
GENAI_API_VERSION = "v1beta"


def make_genai_client(api_key: str) -> Optional[Any]:
    """Build a Gemini client pinned to the API version this project targets."""
    if not genai or not api_key:
        return None
    if types is None:  # pragma: no cover - older SDKs without HttpOptions
        return genai.Client(api_key=api_key)
    return genai.Client(
        api_key=api_key,
        http_options=types.HttpOptions(api_version=GENAI_API_VERSION),
    )
