"""Use cases of the trace viewer: validate, then ask the trace store.

Without tracing configured the store is a ``SourceUnavailable`` and every use
case raises it, before any validation. ``ui_url`` is the tracing backend's own
UI, when configured.
"""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    InvalidTraceQuery,
    SpanKind,
    Trace,
    TraceNotFound,
    TraceQuery,
    TraceStore,
    TraceSummary,
    normalize_trace_id,
)


class TraceService:
    def __init__(self, store: TraceStore | SourceUnavailable, *, ui_url: str | None = None) -> None:
        self._store = store
        self.ui_url = ui_url.rstrip("/") if ui_url else None

    def _traces(self) -> TraceStore:
        if isinstance(self._store, SourceUnavailable):
            raise self._store
        return self._store

    async def services(self) -> list[str]:
        return await self._traces().services()

    async def operations(self, service: str) -> list[tuple[str, SpanKind]]:
        store = self._traces()
        if not service:
            raise InvalidTraceQuery("service is required")
        return await store.operations(service)

    async def search(self, query: TraceQuery) -> list[TraceSummary]:
        store = self._traces()
        query = query.validated()
        return (await store.search(query))[: query.limit]

    async def get(self, trace_id: str) -> Trace:
        store = self._traces()
        trace_id = normalize_trace_id(trace_id)
        trace = await store.get(trace_id)
        if trace is None:
            raise TraceNotFound(trace_id)
        return trace
