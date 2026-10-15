"""Traces, as the Nexus trace viewer shows them: spans laid out from the trace start.

A ``TraceStore`` reads a tracing backend (Jaeger today, over its query API v3).
Times are offsets in milliseconds from the trace start; ids are lowercase hex.
Values match ``/api/admin/system/traces`` field for field (see
``adapters/primary/sysadmin__primary_adapter__traces.py``).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

SpanKind = Literal["server", "client", "producer", "consumer", "internal", ""]
SpanStatus = Literal["ok", "error", "unset"]

LOOKBACKS: dict[str, int] = {"15m": 900, "1h": 3600, "6h": 21_600, "24h": 86_400, "7d": 604_800}
DEFAULT_LOOKBACK = "1h"
MAX_SPANS = 5000
MAX_SEARCH_SERVICES = 25
MAX_LIMIT = 100

_TRACE_ID = re.compile(r"[0-9a-fA-F]{32}")


class InvalidTraceQuery(Exception):
    """A malformed trace id or search (answered 400)."""


class TraceNotFound(Exception):
    """No trace with this id (answered 404)."""

    def __init__(self, trace_id: str) -> None:
        super().__init__(f"trace {trace_id} not found")
        self.trace_id = trace_id


@dataclass(frozen=True)
class SpanEvent:
    name: str
    offset_ms: float  # from the span start
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SpanLink:
    trace_id: str
    span_id: str


@dataclass(frozen=True)
class Span:
    span_id: str
    parent_id: str | None  # None when the parent is not in the trace
    name: str
    service: str
    kind: SpanKind
    start_ms: float  # from the trace start
    duration_ms: float
    status: SpanStatus
    status_message: str = ""
    attributes: dict[str, Any] = field(default_factory=dict)
    resource: dict[str, Any] = field(default_factory=dict)
    events: tuple[SpanEvent, ...] = ()
    links: tuple[SpanLink, ...] = ()


@dataclass(frozen=True)
class ServiceCount:
    name: str
    spans: int
    errors: int


@dataclass(frozen=True)
class TraceRoot:
    service: str
    name: str


@dataclass(frozen=True)
class Trace:
    trace_id: str
    start: str  # ISO 8601 UTC
    duration_ms: float
    services: tuple[ServiceCount, ...]
    spans: tuple[Span, ...]  # by start, then depth
    truncated: bool = False


@dataclass(frozen=True)
class TraceSummary:
    trace_id: str
    root: TraceRoot
    start: str
    duration_ms: float
    spans: int
    errors: int
    services: tuple[ServiceCount, ...]


@dataclass(frozen=True)
class TraceQuery:
    service: str | None = None
    operation: str | None = None
    lookback: str = DEFAULT_LOOKBACK
    min_duration_ms: float | None = None
    max_duration_ms: float | None = None
    errors: bool = False
    limit: int = 20

    def validated(self) -> TraceQuery:
        if self.lookback not in LOOKBACKS:
            raise InvalidTraceQuery(
                f"lookback must be one of {', '.join(LOOKBACKS)}, not {self.lookback!r}"
            )
        if not 1 <= self.limit <= MAX_LIMIT:
            raise InvalidTraceQuery(f"limit must be between 1 and {MAX_LIMIT}")
        for name in ("min_duration_ms", "max_duration_ms"):
            value = getattr(self, name)
            if value is not None and value < 0:
                raise InvalidTraceQuery(f"{name} cannot be negative")
        if (
            self.min_duration_ms is not None
            and self.max_duration_ms is not None
            and self.min_duration_ms > self.max_duration_ms
        ):
            raise InvalidTraceQuery("min_duration_ms is above max_duration_ms")
        return self

    def keeps(self, summary: TraceSummary) -> bool:
        """The filters a backend may not apply itself (errors, durations)."""
        if self.errors and summary.errors == 0:
            return False
        if self.min_duration_ms is not None and summary.duration_ms < self.min_duration_ms:
            return False
        if self.max_duration_ms is not None and summary.duration_ms > self.max_duration_ms:
            return False
        return True


def normalize_trace_id(value: str) -> str:
    """32 hex characters, lowercased; anything else is InvalidTraceQuery."""
    if not isinstance(value, str) or not _TRACE_ID.fullmatch(value.strip()):
        raise InvalidTraceQuery(f"not a trace id: {value!r} (32 hex characters)")
    return value.strip().lower()


def service_counts(spans: tuple[Span, ...] | list[Span]) -> tuple[ServiceCount, ...]:
    counts: dict[str, list[int]] = {}
    for span in spans:
        entry = counts.setdefault(span.service, [0, 0])
        entry[0] += 1
        entry[1] += span.status == "error"
    return tuple(
        ServiceCount(name, n, e)
        for name, (n, e) in sorted(counts.items(), key=lambda item: (-item[1][0], item[0]))
    )


def summarize(trace: Trace) -> TraceSummary:
    roots = [s for s in trace.spans if s.parent_id is None]
    root = min(roots or trace.spans, key=lambda s: s.start_ms, default=None)
    return TraceSummary(
        trace_id=trace.trace_id,
        root=TraceRoot(root.service, root.name) if root else TraceRoot("", ""),
        start=trace.start,
        duration_ms=trace.duration_ms,
        spans=len(trace.spans),
        errors=sum(s.status == "error" for s in trace.spans),
        services=trace.services,
    )


class TraceStore(Protocol):
    """A tracing backend. Every method raises ``SourceUnavailable("tracing", ...)``
    when the backend cannot answer."""

    async def services(self) -> list[str]:
        """Services that reported spans, sorted."""
        ...

    async def operations(self, service: str) -> list[tuple[str, SpanKind]]:
        """(span name, kind) the service reported, sorted by name."""
        ...

    async def search(self, query: TraceQuery) -> list[TraceSummary]:
        """Traces started within ``query.lookback``, newest first, at most ``limit``."""
        ...

    async def get(self, trace_id: str) -> Trace | None:
        """The whole trace (at most ``MAX_SPANS`` spans), or None when unknown."""
        ...
