"""SearchService — federated multi-source search with streaming results.

Holds a registry of `ISearchSource`s (graph, object storage, DuckDuckGo, ...)
and federates a single query across them. Yields `SearchEvent`s as they
arrive so the frontend can render hits without waiting for every source.

Design notes:
- Sync-style (matches the rest of naas_abi_core; BusService callbacks and
  TripleStoreService are all sync). Streaming is implemented with one worker
  thread per source feeding a shared queue, not with asyncio.
- Per-source timeout + try/except: one slow or broken source can't sink the
  whole query — it surfaces as a `SourceError` event and the others continue.
- The service does NOT itself maintain indexes. Indexable sources subscribe
  to upstream domain events (TriplesInserted, object-storage events, ...) on
  their own and publish `SearchIndexFailed` / `DocumentIndexed` via
  EventService when they update. Keeps the dependency arrow clean:
  `search → events → bus`; nothing imports `search`.
- A tiny TTL cache fronts each source so repeated queries (especially for
  rate-limited external sources like DuckDuckGo) don't hammer them.
"""

from __future__ import annotations

import queue
import threading
import time
from typing import Any, Iterator

from naas_abi_core import logger
from naas_abi_core.services.search.SearchPorts import (
    Exceptions,
    Hit,
    ISearchService,
    ISearchSource,
    SearchEvent,
    SearchFinished,
    SearchHit,
    SearchStarted,
    SourceError,
    SourceFinished,
    SourceStarted,
)
from naas_abi_core.services.search.ontologies.modules.SearchEventOntology import (
    IndexRebuilt,
)
from naas_abi_core.services.ServiceBase import ServiceBase


_SENTINEL = object()


class _TTLCache:
    """Tiny per-source TTL cache keyed by (query, filters, limit).

    Held inside the SearchService so each source benefits regardless of how
    it was implemented. TTL is short by default because search results need
    to reflect recent index updates within seconds, not minutes.
    """

    def __init__(self, ttl_seconds: float = 30.0, max_entries: int = 256):
        self._ttl = ttl_seconds
        self._max = max_entries
        self._store: dict[tuple, tuple[float, list[SearchHit]]] = {}
        self._lock = threading.Lock()

    def get(self, key: tuple) -> list[SearchHit] | None:
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            expires_at, hits = entry
            if time.monotonic() > expires_at:
                del self._store[key]
                return None
            return list(hits)

    def put(self, key: tuple, hits: list[SearchHit]) -> None:
        with self._lock:
            if len(self._store) >= self._max:
                # Cheap eviction: drop arbitrary key. Good enough for a 256-
                # entry cache; replace with LRU when usage demands it.
                self._store.pop(next(iter(self._store)))
            self._store[key] = (time.monotonic() + self._ttl, list(hits))


class SearchService(ServiceBase, ISearchService):
    def __init__(self, cache_ttl_seconds: float = 30.0):
        super().__init__()
        self._sources: dict[str, ISearchSource] = {}
        self._cache = _TTLCache(ttl_seconds=cache_ttl_seconds)
        self._lock = threading.Lock()

    # ------------------------------------------------------------------
    # registry
    # ------------------------------------------------------------------

    def register_source(self, source: ISearchSource) -> None:
        with self._lock:
            if source.name in self._sources:
                raise Exceptions.SourceAlreadyRegisteredError(source.name)
            self._sources[source.name] = source

    def list_sources(self) -> list[str]:
        with self._lock:
            return sorted(self._sources.keys())

    def get_source(self, name: str) -> ISearchSource:
        with self._lock:
            try:
                return self._sources[name]
            except KeyError:
                raise Exceptions.SourceNotFoundError(name)

    # ------------------------------------------------------------------
    # search (federated, streaming)
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        *,
        sources: list[str] | None = None,
        filters: dict[str, Any] | None = None,
        limit: int = 50,
        timeout: float = 10.0,
    ) -> Iterator[SearchEvent]:
        with self._lock:
            selected_names = (
                sources if sources is not None else sorted(self._sources.keys())
            )
            for name in selected_names:
                if name not in self._sources:
                    raise Exceptions.SourceNotFoundError(name)
            selected = [self._sources[n] for n in selected_names]

        yield SearchStarted(query=query, sources=selected_names)

        if not selected:
            yield SearchFinished(total_hits=0, duration_ms=0.0)
            return

        # One worker thread per source pushes events into this queue. The
        # main loop yields them in arrival order. Bounded so a runaway
        # source can't grow the queue without bound.
        event_q: queue.Queue = queue.Queue(maxsize=max(64, limit * len(selected)))
        wall_start = time.monotonic()

        for source in selected:
            t = threading.Thread(
                target=self._run_source,
                name=f"search-{source.name}",
                args=(source, query, filters, limit, timeout, event_q),
                daemon=True,
            )
            t.start()

        finished = 0
        total_hits = 0
        while finished < len(selected):
            try:
                evt = event_q.get(timeout=timeout + 5.0)
            except queue.Empty:
                # All worker timeouts should have fired by now; if the queue
                # is still empty, something is genuinely stuck. Surface a
                # SourceError for everything that hasn't reported in.
                logger.warning("SearchService: federation queue drained without finishes")
                break

            if evt is _SENTINEL:
                finished += 1
                continue

            if isinstance(evt, Hit):
                total_hits += 1
            yield evt  # type: ignore[misc]

        yield SearchFinished(
            total_hits=total_hits,
            duration_ms=(time.monotonic() - wall_start) * 1000.0,
        )

    def _run_source(
        self,
        source: ISearchSource,
        query: str,
        filters: dict[str, Any] | None,
        limit: int,
        timeout: float,
        event_q: "queue.Queue[Any]",
    ) -> None:
        """Worker body: emit SourceStarted, drain hits, emit Finished/Error.

        Always emits a `_SENTINEL` last so the main loop can count completions
        deterministically — even on cache-hit, exception, or timeout paths.
        """
        start = time.monotonic()
        event_q.put(SourceStarted(source=source.name))
        try:
            cache_key = (source.name, query, _hashable(filters), limit)
            cached = self._cache.get(cache_key)
            if cached is not None:
                for h in cached:
                    event_q.put(Hit(hit=h))
                event_q.put(
                    SourceFinished(
                        source=source.name,
                        count=len(cached),
                        duration_ms=(time.monotonic() - start) * 1000.0,
                    )
                )
                return

            hits: list[SearchHit] = []
            for hit in _with_timeout(
                source.search(query, filters=filters, limit=limit),
                timeout,
                source.name,
            ):
                event_q.put(Hit(hit=hit))
                hits.append(hit)
                if len(hits) >= limit:
                    break
            self._cache.put(cache_key, hits)
            event_q.put(
                SourceFinished(
                    source=source.name,
                    count=len(hits),
                    duration_ms=(time.monotonic() - start) * 1000.0,
                )
            )
        except Exception as exc:
            event_q.put(
                SourceError(
                    source=source.name,
                    error_type=type(exc).__name__,
                    error_message=str(exc),
                    duration_ms=(time.monotonic() - start) * 1000.0,
                )
            )
        finally:
            event_q.put(_SENTINEL)

    # ------------------------------------------------------------------
    # reindex
    # ------------------------------------------------------------------

    def reindex(self, source_name: str) -> int:
        source = self.get_source(source_name)
        if not source.supports_indexing():
            raise Exceptions.IndexingNotSupportedError(source_name)

        start = time.monotonic()
        count = source.reindex()
        duration_ms = (time.monotonic() - start) * 1000.0
        self._publish_event(
            IndexRebuilt(
                source=source_name,
                document_count=count,
                duration_ms=duration_ms,
            )
        )
        return count

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _publish_event(self, event: object) -> None:
        if not self.services_wired:
            return
        try:
            if not self.services.events_available():
                return
            self.services.events.publish(event)
        except Exception as exc:
            logger.warning(f"SearchService: failed to publish event: {exc}")


def _hashable(filters: dict[str, Any] | None) -> tuple:
    if not filters:
        return ()
    return tuple(sorted((k, repr(v)) for k, v in filters.items()))


def _with_timeout(
    it: Iterator[SearchHit], timeout: float, source_name: str
) -> Iterator[SearchHit]:
    """Bound how long we wait for the FIRST hit from a source.

    Once a source has started producing we let it stream; the global query
    budget is enforced by `limit`. This bounds the "source is unreachable"
    case (DDG down, vector store offline) without truncating slow-but-
    streaming sources.
    """
    deadline = time.monotonic() + timeout
    first = True
    while True:
        if first and time.monotonic() > deadline:
            raise TimeoutError(f"Source '{source_name}' did not respond within {timeout}s")
        try:
            hit = next(it)
        except StopIteration:
            return
        first = False
        yield hit
