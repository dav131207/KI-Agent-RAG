"""
Abstract LLM provider interface.

This keeps the rest of the application vendor-agnostic: today Gemini,
tomorrow OpenAI, Anthropic or a local model.
"""

from abc import ABC, abstractmethod
from typing import AsyncGenerator, Optional


class LLMProvider(ABC):
    """Base class for all LLM providers."""

    @abstractmethod
    def generate(self, model: str, contents: list, **kwargs) -> str:
        """Generate a complete text response."""
        ...

    @abstractmethod
    def stream(self, model: str, contents: list, **kwargs) -> AsyncGenerator[str, None]:
        """Yield text chunks as they are generated."""
        ...

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """Return True when the provider is ready to use."""
        ...


class LLMError(Exception):
    """Raised when an LLM provider fails."""

    def __init__(self, message: str, status_code: int = 500):
        super().__init__(message)
        self.status_code = status_code
