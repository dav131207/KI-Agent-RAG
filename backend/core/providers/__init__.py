"""Provider factory. Add new providers here and register them below."""

from core.config import LLM_PROVIDER
from core.providers.base import LLMProvider
from core.providers.gemini import GeminiProvider

_PROVIDERS: dict[str, type[LLMProvider]] = {
    "gemini": GeminiProvider,
}


def get_llm_provider(provider_name: str | None = None) -> LLMProvider:
    """Return a configured LLM provider instance."""
    name = (provider_name or LLM_PROVIDER).lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(f"Unknown LLM provider: {name}")
    return provider_cls()
