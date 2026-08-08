"""
Simple TTL cache for expensive or repetitive operations.

Designed to be replaced by Redis later without changing the interface.
"""

import hashlib
import json
import time
from typing import Any, Callable, Optional, TypeVar

T = TypeVar("T")


class TTLCache:
    """Thread-safe in-memory cache with time-to-live."""

    def __init__(self, default_ttl: int = 3600):
        self._default_ttl = default_ttl
        self._store: dict[str, tuple[Any, float]] = {}

    def _key(self, *parts: Any) -> str:
        """Create a stable cache key from arbitrary arguments."""
        raw = json.dumps(parts, sort_keys=True, default=str)
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def get(self, *parts: Any) -> Optional[Any]:
        """Return a cached value if it has not expired."""
        key = self._key(*parts)
        entry = self._store.get(key)
        if not entry:
            return None
        value, expires = entry
        if time.time() > expires:
            del self._store[key]
            return None
        return value

    def set(self, value: Any, *parts: Any, ttl: Optional[int] = None) -> None:
        """Store a value with an optional custom TTL."""
        key = self._key(*parts)
        expires = time.time() + (ttl if ttl is not None else self._default_ttl)
        self._store[key] = (value, expires)

    def cached(
        self, ttl: Optional[int] = None
    ) -> Callable[[Callable[..., T]], Callable[..., T]]:
        """Decorator that caches a function's return value."""

        def decorator(func: Callable[..., T]) -> Callable[..., T]:
            def wrapper(*args: Any, **kwargs: Any) -> T:
                key_parts = (func.__name__, args, kwargs)
                cached_value = self.get(*key_parts)
                if cached_value is not None:
                    return cached_value
                result = func(*args, **kwargs)
                self.set(result, *key_parts, ttl=ttl)
                return result

            return wrapper

        return decorator


cache = TTLCache(default_ttl=3600)
