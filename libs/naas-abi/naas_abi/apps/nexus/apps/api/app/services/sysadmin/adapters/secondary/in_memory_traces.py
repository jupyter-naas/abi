"""A ``TraceStore`` over traces held in memory (tests, demos)."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    LOOKBACKS,
    SpanKind,
    Trace,
    TraceQuery,
    TraceSummary,
    summarize,
)

SOURCE = "tracing"


class InMemoryTraceStore:
    def __init__(
        self,
        traces: Iterable[Trace] = (),
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        fail: str | None = None,
    ) -> None:
        self._traces = {t.trace_id: t for t in traces}
        self._clock = clock
        self._fail = fail
        self.searches: list[TraceQuery] = []

    def _check(self) -> None:
        if self._fail:
            raise SourceUnavailable(SOURCE, self._fail)

    async def services(self) -> list[str]:
        self._check()
        return sorted({s.service for t in self._traces.values() for s in t.spans})

    async def operations(self, service: str) -> list[tuple[str, SpanKind]]:
        self._check()
        return sorted(
            {
                (s.name, s.kind)
                for t in self._traces.values()
                for s in t.spans
                if s.service == service
            }
        )

    def _matches(self, trace: Trace, query: TraceQuery, since: datetime) -> bool:
        if datetime.fromisoformat(trace.start) < since:
            return False
        return any(
            (query.service is None or s.service == query.service)
            and (query.operation is None or s.name == query.operation)
            for s in trace.spans
        )

    async def search(self, query: TraceQuery) -> list[TraceSummary]:
        self._check()
        self.searches.append(query)
        since = self._clock() - timedelta(seconds=LOOKBACKS[query.lookback])
        found = [
            summary
            for trace in self._traces.values()
            if self._matches(trace, query, since) and query.keeps(summary := summarize(trace))
        ]
        found.sort(key=lambda s: datetime.fromisoformat(s.start), reverse=True)
        return found[: query.limit]

    async def get(self, trace_id: str) -> Trace | None:
        self._check()
        return self._traces.get(trace_id.lower())
