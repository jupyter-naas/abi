"""Traces from Jaeger's query API v3, for the Nexus trace viewer.

Jaeger searches one service at a time: a search without a service asks the
first ``max_services`` services (sorted) and merges their answers by trace id.
Jaeger filters by service, operation and time; trace-level filters (errors,
durations) run here, over a deeper search. Jaeger answers 404 when a search
or a trace finds nothing. Responses are OTLP JSON (``otlp_json``).
"""

from __future__ import annotations

import asyncio
import contextlib
import time
from collections.abc import AsyncIterator, Callable
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.otlp_json import (
    KINDS,
    to_traces,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    LOOKBACKS,
    MAX_SEARCH_SERVICES,
    MAX_SPANS,
    SpanKind,
    Trace,
    TraceQuery,
    TraceSummary,
    summarize,
)

SOURCE = "tracing"
FILTERED_DEPTH = 5  # traces asked per trace wanted when filtering here
MAX_DEPTH = 500
_KINDS: dict[str, SpanKind] = {kind: kind for kind in KINDS.values()}


def _rfc3339(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat().replace("+00:00", "Z")


def _kind(value: Any) -> SpanKind:
    """``server`` or ``SPAN_KIND_SERVER`` to ``server``; unknown kinds to ``""``."""
    name = str(value or "").lower().removeprefix("span_kind_")
    return _KINDS.get(name, "")


def _default_client(base_url: str, timeout: float) -> Any:
    import httpx

    return httpx.AsyncClient(base_url=base_url, timeout=timeout)


class JaegerTraceStore:
    source = SOURCE

    def __init__(
        self,
        query_url: str,
        *,
        timeout_seconds: float = 10.0,
        max_services: int = MAX_SEARCH_SERVICES,
        max_spans: int = MAX_SPANS,
        client_factory: Callable[[str, float], Any] = _default_client,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._url = query_url.rstrip("/")
        self._timeout = timeout_seconds
        self._max_services = max_services
        self._max_spans = max_spans
        self._client_factory = client_factory
        self._clock = clock

    @contextlib.asynccontextmanager
    async def _client(self) -> AsyncIterator[Any]:
        client = self._client_factory(self._url, self._timeout)
        try:
            yield client
        finally:
            with contextlib.suppress(Exception):
                await client.aclose()

    async def _get(self, client: Any, path: str, params: dict[str, Any] | None = None) -> Any:
        """The JSON body, None on 404; SourceUnavailable when Jaeger cannot answer."""
        try:
            response = await client.get(path, params=params)
        except Exception as exc:  # noqa: BLE001 - unreachable, refused, timed out
            raise SourceUnavailable(
                SOURCE, f"jaeger at {self._url}: {str(exc) or type(exc).__name__}"
            ) from exc
        if response.status_code == 404:
            return None
        if response.status_code >= 400:
            raise SourceUnavailable(
                SOURCE, f"jaeger answered {response.status_code}: {response.text[:200]}"
            )
        try:
            return response.json()
        except ValueError as exc:
            raise SourceUnavailable(SOURCE, f"jaeger at {self._url} did not answer JSON") from exc

    async def _services(self, client: Any) -> list[str]:
        body = await self._get(client, "/api/v3/services") or {}
        return sorted({str(n) for n in body.get("services") or () if n and n != "jaeger"})

    async def services(self) -> list[str]:
        async with self._client() as client:
            return await self._services(client)

    async def operations(self, service: str) -> list[tuple[str, SpanKind]]:
        async with self._client() as client:
            body = await self._get(client, "/api/v3/operations", {"service": service}) or {}
        found = {
            (str(op.get("name") or ""), _kind(op.get("spanKind")))
            for op in body.get("operations") or ()
            if op.get("name")
        }
        return sorted(found)

    def _params(self, query: TraceQuery, service: str) -> dict[str, Any]:
        end = self._clock()
        filtered = (
            query.errors or query.min_duration_ms is not None or query.max_duration_ms is not None
        )
        params: dict[str, Any] = {
            "query.service_name": service,
            "query.start_time_min": _rfc3339(end - LOOKBACKS[query.lookback]),
            "query.start_time_max": _rfc3339(end),
            "query.search_depth": (
                min(query.limit * FILTERED_DEPTH, MAX_DEPTH) if filtered else query.limit
            ),
        }
        if query.operation:
            params["query.operation_name"] = query.operation
        return params

    async def search(self, query: TraceQuery) -> list[TraceSummary]:
        query = query.validated()
        async with self._client() as client:
            if query.service:
                services = [query.service]
            else:
                services = (await self._services(client))[: self._max_services]
            bodies = await asyncio.gather(
                *(
                    self._get(client, "/api/v3/traces", self._params(query, service))
                    for service in services
                )
            )
        traces = to_traces([b for b in bodies if b], max_spans=self._max_spans)
        found = [summary for t in traces if query.keeps(summary := summarize(t))]
        found.sort(key=lambda s: datetime.fromisoformat(s.start), reverse=True)
        return found[: query.limit]

    async def get(self, trace_id: str) -> Trace | None:
        trace_id = trace_id.lower()
        async with self._client() as client:
            body = await self._get(client, f"/api/v3/traces/{trace_id}")
        if not body:
            return None
        return next(
            (t for t in to_traces(body, max_spans=self._max_spans) if t.trace_id == trace_id),
            None,
        )
