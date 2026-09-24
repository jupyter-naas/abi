"""In-process cache for dataset search HTTP responses.

Entries are scoped to a *read generation* that advances only when envelope
sync actually changes namespace ``x`` tables (event sensor or files scheduler).
"""

from __future__ import annotations

import hashlib
import threading
from collections.abc import Callable
from typing import Any, Literal

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    PROJECTION_COMMITS_V1,
    X_DATASET_NAMESPACE,
)

READ_GENERATION_KV_KEY = "x/apps/x_proxy/dataset/read_generation"

SearchScope = Literal["posts", "users"]

_MAX_ENTRIES = 2048


def _cache_key(scope: SearchScope, query: str, page: int, per_page: int) -> tuple[str, ...]:
    return (scope, query.strip().casefold()[:200], str(page), str(per_page))


def _etag(generation: str, key: tuple[str, ...]) -> str:
    payload = generation + "\0" + "\0".join(key)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:32]
    return f'W/"{generation}-{digest}"'


def _cache_control_headers(etag: str) -> dict[str, str]:
    return {
        "ETag": etag,
        "Cache-Control": "private, max-age=31536000, immutable",
    }


class DatasetSearchResponseCache:
    """Thread-safe response bodies keyed by (generation, search params)."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._generation: str | None = None
        self._entries: dict[tuple[str, ...], bytes] = {}

    def get(self, generation: str, key: tuple[str, ...]) -> bytes | None:
        with self._lock:
            if generation != self._generation:
                return None
            return self._entries.get(key)

    def put(self, generation: str, key: tuple[str, ...], body: bytes) -> None:
        with self._lock:
            if generation != self._generation:
                self._entries.clear()
                self._generation = generation
            if len(self._entries) >= _MAX_ENTRIES:
                self._entries.clear()
            self._entries[key] = body


SEARCH_RESPONSE_CACHE = DatasetSearchResponseCache()


def optional_module_kv(module: Any | None) -> Any | None:
    """KV when the hosting module is allowed to use it (else SQL generation fallback)."""
    if module is None:
        return None
    try:
        return module.engine.services.kv
    except (ValueError, AttributeError):
        return None


def publish_read_cache_generation(module, commit_id: str) -> None:
    """Call after a dataset sync batch that changed projection tables."""
    commit_id = str(commit_id or "").strip()
    if not commit_id:
        return
    kv = optional_module_kv(module)
    if kv is None:
        return
    try:
        kv.set(READ_GENERATION_KV_KEY, commit_id.encode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"x dataset read_cache: could not publish generation ({exc})")


def read_cache_generation(dataset, *, kv: Any | None = None) -> str:
    """Current generation token for search response caching."""
    if kv is not None:
        try:
            raw = kv.get(READ_GENERATION_KV_KEY)
        except Exception:  # noqa: BLE001
            raw = None
        if raw:
            try:
                text = (
                    raw.decode("utf-8")
                    if isinstance(raw, (bytes, bytearray))
                    else str(raw)
                )
            except UnicodeDecodeError:
                text = ""
            text = text.strip()
            if text:
                return text

    result = dataset.query(
        f"SELECT commit_id FROM {PROJECTION_COMMITS_V1} "
        f"WHERE envelope_count > 0 "
        f"ORDER BY committed_at DESC LIMIT 1",
        namespace=X_DATASET_NAMESPACE,
    )
    if result.rows:
        return str(result.rows[0].get("commit_id") or "0")
    return "0"


def cached_search_response(
    *,
    if_none_match: str | None,
    generation: str,
    scope: SearchScope,
    query: str,
    page: int,
    per_page: int,
    compute_body: Callable[[], bytes],
) -> tuple[int, bytes, dict[str, str]]:
    """Return (status_code, body, headers) for a search JSON response."""
    key = _cache_key(scope, query, page, per_page)
    etag = _etag(generation, key)
    headers = _cache_control_headers(etag)
    if if_none_match == etag:
        body = SEARCH_RESPONSE_CACHE.get(generation, key)
        if body is not None:
            return 304, b"", headers

    body = SEARCH_RESPONSE_CACHE.get(generation, key)
    if body is None:
        body = compute_body()
        if isinstance(body, str):
            body = body.encode("utf-8")
        SEARCH_RESPONSE_CACHE.put(generation, key, body)
    return 200, body, headers
