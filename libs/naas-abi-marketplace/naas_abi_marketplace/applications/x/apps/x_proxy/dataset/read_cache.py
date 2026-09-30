"""In-process cache for dataset-backed X Proxy HTTP responses.

Entries are stamped with the *read generation* they were computed at; the
generation advances only when envelope sync actually changes namespace ``x``
tables (event sensor or files scheduler).

During ingest the generation moves every few minutes, and a cold dataset query
costs about a second, so a cache that simply dropped everything on each advance
would be cold most of the time. Instead it is **stale-while-revalidate**: a
request whose entry belongs to an older generation gets that body at once while
one background refresh recomputes it. Only a request never seen before waits
for the query, and concurrent identical ones share a single computation.
"""

from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal

from naas_abi_core import logger
from naas_abi_marketplace.applications.x.apps.x_proxy.dataset.store import (
    PROJECTION_COMMITS_V1,
    X_DATASET_NAMESPACE,
)

READ_GENERATION_KV_KEY = "x/apps/x_proxy/dataset/read_generation"

SearchScope = Literal["posts", "users"]

CacheKey = tuple[str, ...]

_MAX_ENTRIES = 2048
# Background refreshes run dataset queries; two keeps them from crowding out
# the requests that are actually waiting.
_REFRESH_WORKERS = 2


def search_cache_key(
    scope: SearchScope, query: str, page: int, per_page: int
) -> CacheKey:
    return (scope, query.strip().casefold()[:200], str(page), str(per_page))


def _etag(generation: str, key: CacheKey) -> str:
    payload = generation + "\0" + "\0".join(key)
    digest = hashlib.sha256(payload.encode()).hexdigest()[:32]
    return f'W/"{generation}-{digest}"'


def _cache_control_headers(etag: str) -> dict[str, str]:
    # The URL does not carry the generation, so the browser must revalidate:
    # ``no-cache`` + ETag makes an unchanged answer a bodiless 304.
    return {
        "ETag": etag,
        "Cache-Control": "private, no-cache",
    }


class DatasetSearchResponseCache:
    """Thread-safe LRU of response bodies, each stamped with its generation."""

    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._lock = threading.Lock()
        self._max_entries = max_entries
        self._entries: OrderedDict[CacheKey, tuple[str, bytes]] = OrderedDict()
        self._computing: dict[CacheKey, threading.Lock] = {}
        self._refreshing: set[CacheKey] = set()
        self._executor: ThreadPoolExecutor | None = None

    def get(self, generation: str, key: CacheKey) -> bytes | None:
        """The body for ``key`` if it was computed at ``generation``."""
        entry = self.lookup(key)
        if entry is None or entry[0] != generation:
            return None
        return entry[1]

    def lookup(self, key: CacheKey) -> tuple[str, bytes] | None:
        """``(generation, body)`` for ``key`` whatever its generation."""
        with self._lock:
            entry = self._entries.get(key)
            if entry is not None:
                self._entries.move_to_end(key)
            return entry

    def put(self, generation: str, key: CacheKey, body: bytes) -> None:
        with self._lock:
            self._entries[key] = (generation, body)
            self._entries.move_to_end(key)
            while len(self._entries) > self._max_entries:
                self._entries.popitem(last=False)

    def compute(
        self, generation: str, key: CacheKey, compute_body: Callable[[], bytes]
    ) -> bytes:
        """Compute and store ``key`` once, however many callers ask at once."""
        with self._lock:
            gate = self._computing.setdefault(key, threading.Lock())
        with gate:
            body = self.get(generation, key)
            if body is None:
                body = compute_body()
                if isinstance(body, str):
                    body = body.encode("utf-8")
                self.put(generation, key, body)
        with self._lock:
            if self._computing.get(key) is gate and not gate.locked():
                del self._computing[key]
        return body

    def refresh_async(
        self, generation: str, key: CacheKey, compute_body: Callable[[], bytes]
    ) -> None:
        """Recompute ``key`` in the background unless a refresh is under way."""
        with self._lock:
            if key in self._refreshing:
                return
            self._refreshing.add(key)
            if self._executor is None:
                self._executor = ThreadPoolExecutor(
                    max_workers=_REFRESH_WORKERS,
                    thread_name_prefix="x-proxy-read-cache",
                )
            executor = self._executor

        def run() -> None:
            try:
                self.compute(generation, key, compute_body)
            except Exception as exc:  # noqa: BLE001
                # The stale body keeps being served; the next request retries.
                logger.warning(f"x dataset read_cache: refresh of {key} failed ({exc})")
            finally:
                with self._lock:
                    self._refreshing.discard(key)

        executor.submit(run)


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


def cached_dataset_response(
    *,
    if_none_match: str | None,
    generation: str,
    key: CacheKey,
    compute_body: Callable[[], bytes],
    cache: DatasetSearchResponseCache = SEARCH_RESPONSE_CACHE,
) -> tuple[int, bytes, dict[str, str]]:
    """Return (status_code, body, headers) for any dataset JSON response.

    A body from an older generation is answered straight away (its own ETag,
    so the browser will ask again) and refreshed in the background.
    """
    entry = cache.lookup(key)
    if entry is None:
        body = cache.compute(generation, key, compute_body)
        body_generation = generation
    else:
        body_generation, body = entry
        if body_generation != generation:
            cache.refresh_async(generation, key, compute_body)
    headers = _cache_control_headers(_etag(body_generation, key))
    if if_none_match == headers["ETag"]:
        return 304, b"", headers
    return 200, body, headers


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
    return cached_dataset_response(
        if_none_match=if_none_match,
        generation=generation,
        key=search_cache_key(scope, query, page, per_page),
        compute_body=compute_body,
    )
