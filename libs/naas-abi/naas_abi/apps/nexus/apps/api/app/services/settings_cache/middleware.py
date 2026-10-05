"""Cache the API answers the Nexus settings pages read, for 24 hours.

Opt-in: only GET requests carrying ``X-Nexus-Cache: 1`` are cached. The web app sends
that header from settings pages only, so the rest of the app always reads live data.

Keys are per user (the bearer token's ``sub``, not the token itself, which rotates)
and include the full path and query string, so role-dependent answers never leak
between users.

Invalidation uses two generation counters stored in the cache itself:

* a global one, bumped after any successful write (POST/PUT/PATCH/DELETE) to a
  settings route, so a change made by anyone is visible to everyone on the next read;
* a per-user one, bumped by ``POST /api/settings-cache/refresh`` (the Reload button),
  which drops only the caller's entries.

The global one is also bumped when the API starts (``invalidate_on_startup``): an ABI
restart is the only event that clears the whole cache on its own. Rebuilding or
restarting the web app does not.

The cache is best effort: any cache failure falls through to the live endpoint.
Pure ASGI, and registered inside CORS so cached answers still carry CORS headers.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import logging
from collections.abc import Callable
from typing import Any

from naas_abi_core.services.cache.CachePort import CacheExpiredError, CacheNotFoundError
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import Headers
from starlette.types import ASGIApp, Message, Receive, Scope, Send

logger = logging.getLogger(__name__)

CACHE_HEADER = "X-Nexus-Cache"
REFRESH_PATH = "/api/settings-cache/refresh"
DEFAULT_TTL = datetime.timedelta(hours=24)

# API routes read by the workspace and organization settings pages.
SETTINGS_PATH_PREFIXES: tuple[str, ...] = (
    "/api/agents",
    "/api/skills",
    "/api/workspaces",
    "/api/organizations",
    "/api/providers",
    "/api/secrets",
    "/api/apps",
    "/api/search/topics",
    "/api/graph/list",
)

_WRITE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_KEY_PREFIX = "nexus-settings-api"
_GLOBAL_GENERATION_KEY = f"{_KEY_PREFIX}:generation:global"


_FALLBACK_CACHE: Any = None


def _user_generation_key(user_id: str) -> str:
    return f"{_KEY_PREFIX}:generation:user:{user_id}"


def default_cache_resolver() -> Any:
    """The engine's (multi-tier) cache, else a local filesystem cache."""
    try:
        from naas_abi import ABIModule

        services = ABIModule.get_instance().engine.services
        if services.cache_available():
            return services.cache
    except Exception:  # noqa: BLE001 - engine not ready → local cache
        pass
    global _FALLBACK_CACHE
    if _FALLBACK_CACHE is None:
        from naas_abi_core.services.cache.CacheFactory import CacheFactory

        _FALLBACK_CACHE = CacheFactory.CacheFS_find_storage(subpath="nexus/settings-api")
    return _FALLBACK_CACHE


def _read_generation(cache: Any, key: str) -> int:
    try:
        value = cache.get(key)
    except (CacheNotFoundError, CacheExpiredError):
        return 0
    return int((value or {}).get("v", 0))


def _store_json(cache: Any, key: str, value: dict[str, Any]) -> None:
    cache.set_json(key, value)  # cold tier (durable)
    if cache.hot_available():
        cache.hot.set_json(key, value)  # hot tier (fast reads)


def _bump_generation(cache: Any, key: str) -> None:
    _store_json(cache, key, {"v": _read_generation(cache, key) + 1})


def invalidate_all(cache: Any) -> None:
    """Drop every cached settings answer, for every user."""
    _bump_generation(cache, _GLOBAL_GENERATION_KEY)


def invalidate_on_startup(cache_resolver: Callable[[], Any] = default_cache_resolver) -> None:
    """Called when the API starts: answers cached before a restart are never served."""
    try:
        invalidate_all(cache_resolver())
        logger.info("Settings cache invalidated on startup")
    except Exception as exc:  # noqa: BLE001 - never block startup on the cache
        logger.warning("Settings cache: startup invalidation failed: %s", exc)


def default_user_resolver(headers: Headers) -> str | None:
    from naas_abi.apps.nexus.apps.api.app.services.identity_events.middleware import (
        user_id_from_headers,
    )

    return user_id_from_headers(headers)


def is_settings_path(path: str) -> bool:
    return any(
        path == prefix or path.startswith(prefix + "/") or path.startswith(prefix + "?")
        for prefix in SETTINGS_PATH_PREFIXES
    )


class SettingsCacheMiddleware:
    def __init__(
        self,
        app: ASGIApp,
        cache_resolver: Callable[[], Any] = default_cache_resolver,
        user_resolver: Callable[[Headers], str | None] = default_user_resolver,
        ttl: datetime.timedelta = DEFAULT_TTL,
    ) -> None:
        self.app = app
        self.cache_resolver = cache_resolver
        self.user_resolver = user_resolver
        self.ttl = ttl

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method: str = scope.get("method", "GET").upper()
        path: str = scope.get("path", "")

        if path == REFRESH_PATH:
            await self._handle_refresh(scope, receive, send, method)
            return
        if not is_settings_path(path):
            await self.app(scope, receive, send)
            return
        if method in _WRITE_METHODS:
            await self._handle_write(scope, receive, send)
            return

        headers = Headers(scope=scope)
        if method != "GET" or headers.get(CACHE_HEADER) != "1":
            await self.app(scope, receive, send)
            return
        user_id = self.user_resolver(headers)
        if not user_id:
            await self.app(scope, receive, send)
            return

        key = await self._entry_key(user_id, path, scope.get("query_string", b""))
        if key is None:
            await self.app(scope, receive, send)
            return

        cached = await self._read(key)
        if cached is not None:
            await self._send_cached(send, cached)
            return
        await self._forward_and_store(scope, receive, send, key)

    # ------------------------------------------------------------------
    # Request kinds
    # ------------------------------------------------------------------

    async def _handle_refresh(
        self, scope: Scope, receive: Receive, send: Send, method: str
    ) -> None:
        if method == "OPTIONS":
            await self.app(scope, receive, send)
            return
        if method != "POST":
            await _send_plain(send, 405)
            return
        user_id = self.user_resolver(Headers(scope=scope))
        if not user_id:
            await _send_plain(send, 401)
            return
        await self._bump(_user_generation_key(user_id))
        await _send_plain(send, 204)

    async def _handle_write(self, scope: Scope, receive: Receive, send: Send) -> None:
        status = 500

        async def send_wrapper(message: Message) -> None:
            nonlocal status
            if message["type"] == "http.response.start":
                status = int(message.get("status", 500))
            await send(message)

        await self.app(scope, receive, send_wrapper)
        if 200 <= status < 400:
            await self._bump(_GLOBAL_GENERATION_KEY)

    async def _forward_and_store(
        self, scope: Scope, receive: Receive, send: Send, key: str
    ) -> None:
        start: Message | None = None
        body = bytearray()

        async def send_wrapper(message: Message) -> None:
            nonlocal start
            if message["type"] == "http.response.start":
                start = message
                raw_headers = list(message.get("headers", []))
                raw_headers.append((CACHE_HEADER.lower().encode(), b"MISS"))
                message = {**message, "headers": raw_headers}
            elif message["type"] == "http.response.body":
                body.extend(message.get("body", b"") or b"")
            await send(message)

        await self.app(scope, receive, send_wrapper)

        if start is None or int(start.get("status", 500)) != 200:
            return
        response_headers = Headers(raw=list(start.get("headers", [])))
        content_type = response_headers.get("content-type", "")
        if not content_type.startswith("application/json") or "set-cookie" in response_headers:
            return
        try:
            text = bytes(body).decode("utf-8")
        except UnicodeDecodeError:
            return
        await self._write(key, {"content_type": content_type, "body": text})

    # ------------------------------------------------------------------
    # Cache access (blocking cache I/O runs in the threadpool)
    # ------------------------------------------------------------------

    async def _entry_key(self, user_id: str, path: str, query_string: bytes) -> str | None:
        try:
            global_gen = await self._generation(_GLOBAL_GENERATION_KEY)
            user_gen = await self._generation(_user_generation_key(user_id))
        except Exception as exc:  # noqa: BLE001
            logger.warning("Settings cache unavailable, serving live: %s", exc)
            return None
        query = "&".join(sorted(query_string.decode("latin-1").split("&"))) if query_string else ""
        digest = hashlib.sha256(f"{user_id}|{path}?{query}".encode()).hexdigest()
        return f"{_KEY_PREFIX}:entry:{global_gen}:{user_gen}:{digest}"

    async def _generation(self, key: str) -> int:
        return await run_in_threadpool(_read_generation, self.cache_resolver(), key)

    async def _bump(self, key: str) -> None:
        try:
            await run_in_threadpool(_bump_generation, self.cache_resolver(), key)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Settings cache: could not invalidate %s: %s", key, exc)

    async def _read(self, key: str) -> dict[str, Any] | None:
        cache = self.cache_resolver()
        try:
            return await run_in_threadpool(cache.get, key, self.ttl)
        except (CacheNotFoundError, CacheExpiredError):
            return None
        except Exception as exc:  # noqa: BLE001
            logger.warning("Settings cache read failed, serving live: %s", exc)
            return None

    async def _write(self, key: str, value: dict[str, Any]) -> None:
        try:
            await run_in_threadpool(_store_json, self.cache_resolver(), key, value)
        except Exception as exc:  # noqa: BLE001
            logger.warning("Settings cache write failed: %s", exc)

    @staticmethod
    async def _send_cached(send: Send, cached: dict[str, Any]) -> None:
        body = str(cached.get("body", "")).encode("utf-8")
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [
                    (
                        b"content-type",
                        str(cached.get("content_type") or "application/json").encode(),
                    ),
                    (b"content-length", str(len(body)).encode()),
                    (CACHE_HEADER.lower().encode(), b"HIT"),
                ],
            }
        )
        await send({"type": "http.response.body", "body": body})


async def _send_plain(send: Send, status: int) -> None:
    body = b"" if status == 204 else json.dumps({"detail": _STATUS_TEXT.get(status, "")}).encode()
    headers = (
        []
        if status == 204
        else [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())]
    )
    await send({"type": "http.response.start", "status": status, "headers": headers})
    await send({"type": "http.response.body", "body": body})


_STATUS_TEXT = {401: "Not authenticated", 405: "Method not allowed"}
