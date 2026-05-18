"""
Generic TTL in-memory cache.

Replaces the 11 ad-hoc module-level `cache = { data, at }` dicts in the
Next.js routes with a single typed, async-safe implementation.

Usage:
    _cache: TTLCache[list[FlightState]] = TTLCache(ttl_seconds=30)

    async def fetch() -> list[FlightState]:
        return await _cache.get_or_fetch("key", _do_fetch)
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    def __init__(self, ttl_seconds: int, max_size: int = 1000) -> None:
        self._ttl = ttl_seconds
        self._max_size = max_size
        self._store: dict[str, tuple[T, float]] = {}
        self._lock = asyncio.Lock()

    async def get_or_fetch(self, key: str, fetch: Callable[[], Awaitable[T]]) -> T:
        async with self._lock:
            entry = self._store.get(key)
            if entry is not None:
                value, stored_at = entry
                if time.monotonic() - stored_at < self._ttl:
                    return value

        # Fetch outside the lock so concurrent callers don't deadlock
        try:
            value = await fetch()
        except Exception:
            # On error: serve stale if available, else re-raise
            async with self._lock:
                entry = self._store.get(key)
            if entry is not None:
                return entry[0]
            raise

        async with self._lock:
            self._store[key] = (value, time.monotonic())
            self._evict_if_needed()

        return value

    def get_stale(self, key: str) -> T | None:
        entry = self._store.get(key)
        return entry[0] if entry else None

    def _evict_if_needed(self) -> None:
        if len(self._store) <= self._max_size:
            return
        # Evict oldest entry
        oldest_key = min(self._store, key=lambda k: self._store[k][1])
        del self._store[oldest_key]
