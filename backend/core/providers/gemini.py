"""Google Gemini provider implementation."""

import asyncio
from typing import AsyncGenerator

from core.config import GEMINI_API_KEY
from core.providers.base import LLMError, LLMProvider

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None
    types = None


class GeminiProvider(LLMProvider):
    def __init__(self) -> None:
        self._client = None
        if genai and GEMINI_API_KEY:
            self._client = genai.Client(api_key=GEMINI_API_KEY)

    @property
    def is_configured(self) -> bool:
        return self._client is not None

    def _ensure_ready(self) -> None:
        if not genai:
            raise LLMError("Gemini SDK not installed", status_code=500)
        if not self._client:
            raise LLMError("GEMINI_API_KEY not configured", status_code=500)

    def _to_gemini_contents(self, contents: list) -> list:
        """Convert simple dict contents to Gemini types.Content objects."""
        if types is None:
            return []
        result = []
        for item in contents:
            role = item.get("role", "user")
            text = ""
            parts = item.get("parts", [])
            if parts and isinstance(parts[0], dict):
                text = parts[0].get("text", "")
            result.append(types.Content(role=role, parts=[types.Part(text=text)]))
        return result

    def generate(self, model: str, contents: list, **kwargs) -> str:
        self._ensure_ready()
        config = None
        if "temperature" in kwargs:
            config = types.GenerateContentConfig(temperature=kwargs["temperature"])
            
        response = self._client.models.generate_content(
            model=model,
            contents=self._to_gemini_contents(contents),
            config=config,
        )
        return response.text or ""

    async def stream(self, model: str, contents: list, **kwargs) -> AsyncGenerator[str, None]:
        """
        Yield chunks without blocking the event loop.

        The SDK's stream is a synchronous generator, so iterating it directly
        from a coroutine held the loop for the whole generation: concurrent
        requests were served one after another rather than together. It runs on
        a worker thread and hands chunks over through a queue instead.
        """
        self._ensure_ready()
        config = None
        if "temperature" in kwargs:
            config = types.GenerateContentConfig(temperature=kwargs["temperature"])

        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue(maxsize=64)
        done = object()

        def produce() -> None:
            try:
                for chunk in self._client.models.generate_content_stream(
                    model=model,
                    contents=self._to_gemini_contents(contents),
                    config=config,
                ):
                    text = chunk.text or ""
                    if text:
                        # Bounded queue, so a slow reader cannot let the
                        # producer buffer an entire response in memory.
                        asyncio.run_coroutine_threadsafe(queue.put(text), loop).result()
            except Exception as exc:  # surfaced to the consumer below
                asyncio.run_coroutine_threadsafe(queue.put(exc), loop).result()
            finally:
                asyncio.run_coroutine_threadsafe(queue.put(done), loop).result()

        producer = loop.run_in_executor(None, produce)
        try:
            while True:
                item = await queue.get()
                if item is done:
                    break
                if isinstance(item, Exception):
                    raise LLMError(f"Gemini stream failed: {item}")
                yield item
        finally:
            await producer
