"""Redis-backed cache adapter."""

from __future__ import annotations

import hashlib
import json

import redis as redis_lib
from naas_abi_core.services.cache.CachePort import (
    CachedData,
    CacheNotFoundError,
    ICacheAdapter,
)


class CacheRedisAdapter(ICacheAdapter):
    """Cache adapter that stores entries in Redis.

    Each cache entry is stored as a JSON-serialised ``CachedData`` value under
    the key ``{prefix}:{sha256_of_logical_key}``.  The prefix makes it easy to
    namespace multiple logical caches inside the same Redis instance.

    Args:
        redis_url: Redis connection URL (e.g. ``redis://localhost:6379/0``).
        prefix: Namespace prefix prepended to every Redis key (default ``"naas:cache"``).
        socket_timeout: Optional socket timeout in seconds forwarded to the Redis client.
    """

    def __init__(
        self,
        redis_url: str,
        prefix: str = "naas:cache",
        socket_timeout: float | None = None,
    ) -> None:
        self._prefix = prefix.rstrip(":")
        self._client = redis_lib.Redis.from_url(
            redis_url,
            socket_timeout=socket_timeout,
            decode_responses=True,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _redis_key(self, logical_key: str) -> str:
        digest = hashlib.sha256(logical_key.encode()).hexdigest()
        return f"{self._prefix}:{digest}"

    # ------------------------------------------------------------------
    # ICacheAdapter implementation
    # ------------------------------------------------------------------

    def get(self, key: str) -> CachedData:
        raw = self._client.get(self._redis_key(key))
        if raw is None:
            raise CacheNotFoundError(f"Cache entry not found: {key}")
        return CachedData(**json.loads(raw))

    def set(self, key: str, value: CachedData) -> None:
        self._client.set(self._redis_key(key), json.dumps(value.model_dump()))

    def set_if_absent(self, key: str, value: CachedData) -> bool:
        """Atomic set-if-not-exists using Redis NX flag.

        Returns True if the key was set, False if it already existed.
        """
        result = self._client.set(
            self._redis_key(key),
            json.dumps(value.model_dump()),
            nx=True,
        )
        return bool(result)

    def delete(self, key: str) -> None:
        deleted = self._client.delete(self._redis_key(key))
        if deleted == 0:
            raise CacheNotFoundError(f"Cache entry not found: {key}")

    def exists(self, key: str) -> bool:
        return bool(self._client.exists(self._redis_key(key)))
