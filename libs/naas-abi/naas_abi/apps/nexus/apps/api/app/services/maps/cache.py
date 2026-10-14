"""Maps hot-path cache on the engine's ``CacheService`` (naas_abi_core/services/cache).

Opening a map fires many requests at once (layer data, logos). What they
resolve to — membership, a layer's object, the objects themselves — is kept in
the engine cache's **hot** tier (Redis) for a short TTL. The cold tier is object
storage, the very thing being read, so it is never used here.

Any cache failure (no hot tier, Redis down) is a miss: the caller loads as if
there were no cache. Concurrent misses for one key in this process share a
single load (``json_or_load``).
"""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Awaitable, Callable
from typing import Any

from naas_abi_core import logger

# A removed member keeps reading map data for at most this long.
MEMBER_TTL = datetime.timedelta(seconds=30)


class MapsCache:
    def __init__(self, cache: Any | None):
        self._hot = None
        try:
            if cache is not None and cache.hot_available():
                self._hot = cache.hot
        except Exception:  # noqa: BLE001 - a broken cache must never break Maps
            self._hot = None
        self._loading: dict[str, asyncio.Future[Any]] = {}

    def _get(self, key: str, ttl: datetime.timedelta) -> Any | None:
        if self._hot is None:
            return None
        try:
            return self._hot.get(key, ttl)
        except Exception:  # noqa: BLE001 - missing, expired or unreachable: a miss
            return None

    def _set(self, setter: str, key: str, value: Any) -> None:
        if self._hot is None:
            return
        try:
            getattr(self._hot, setter)(key, value)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"Maps cache: could not store {key}: {exc}")

    def get_json(self, key: str, ttl: datetime.timedelta) -> Any | None:
        return self._get(key, ttl)

    def set_json(self, key: str, value: Any) -> None:
        self._set("set_json", key, value)

    def get_binary(self, key: str, ttl: datetime.timedelta) -> bytes | None:
        value = self._get(key, ttl)
        return value if isinstance(value, bytes) else None

    def set_binary(self, key: str, value: bytes) -> None:
        self._set("set_binary", key, value)

    def delete(self, key: str) -> None:
        if self._hot is None:
            return
        try:
            self._hot.delete(key)
        except Exception:  # noqa: BLE001 - absent already
            pass

    async def member(
        self, user_id: str, workspace_id: str, check: Callable[[], Awaitable[Any]]
    ) -> None:
        """Run the workspace membership ``check`` once per user and workspace and
        TTL; it raises for outsiders (never cached)."""

        async def role() -> dict[str, str]:
            return {"role": str(await check())}

        await self.json_or_load(f"nexus:maps:member:{user_id}:{workspace_id}", MEMBER_TTL, role)

    async def json_or_load(
        self, key: str, ttl: datetime.timedelta, load: Callable[[], Awaitable[Any]]
    ) -> Any:
        """The cached JSON value, else ``load()``'s (stored); failures are not stored."""
        value = self.get_json(key, ttl)
        if value is not None:
            return value
        pending = self._loading.get(key)
        if pending is not None:
            return await asyncio.shield(pending)
        future: asyncio.Future[Any] = asyncio.get_running_loop().create_future()
        self._loading[key] = future
        try:
            value = await load()
        except BaseException as exc:
            future.set_exception(exc)
            future.exception()  # retrieved: no warning when nobody else waits
            raise
        else:
            self.set_json(key, value)
            future.set_result(value)
            return value
        finally:
            self._loading.pop(key, None)
