"""OTLP JSON (``resourceSpans``), as Jaeger's query API v3 returns it, to domain traces.

Shared by the live traffic tap and the trace store. int64 values travel as
strings; ids are hex in Jaeger v3 (base64 in some OTLP JSON encoders, accepted).
"""

from __future__ import annotations

import base64
import binascii
import json
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    MAX_SPANS,
    Span,
    SpanEvent,
    SpanKind,
    SpanLink,
    SpanStatus,
    Trace,
    service_counts,
)

KINDS: dict[int, SpanKind] = {1: "internal", 2: "server", 3: "client", 4: "producer", 5: "consumer"}
_KIND_NAMES: dict[str, int] = {
    "SPAN_KIND_INTERNAL": 1,
    "SPAN_KIND_SERVER": 2,
    "SPAN_KIND_CLIENT": 3,
    "SPAN_KIND_PRODUCER": 4,
    "SPAN_KIND_CONSUMER": 5,
}
_STATUS_NAMES: dict[str, int] = {
    "STATUS_CODE_UNSET": 0,
    "STATUS_CODE_OK": 1,
    "STATUS_CODE_ERROR": 2,
}


def int_value(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def attribute_value(value: dict[str, Any]) -> Any:
    """A plain Python value: arrays as lists, key-value lists as dicts, bytes as base64."""
    for key in ("stringValue", "boolValue", "doubleValue"):
        if key in value:
            return value[key]
    if "intValue" in value:
        return int_value(value["intValue"])
    if "bytesValue" in value:
        return value["bytesValue"]
    if "arrayValue" in value:
        return [attribute_value(v or {}) for v in (value["arrayValue"] or {}).get("values") or ()]
    if "kvlistValue" in value:
        return attributes((value["kvlistValue"] or {}).get("values"))
    return None


def attributes(items: Any) -> dict[str, Any]:
    return {item.get("key"): attribute_value(item.get("value") or {}) for item in items or ()}


def flatten(values: dict[str, Any]) -> dict[str, Any]:
    """Scalars kept; arrays and maps as JSON strings (what the viewer lists)."""
    return {
        str(k): json.dumps(v, default=str) if isinstance(v, (list, dict)) else v
        for k, v in values.items()
    }


def resource_spans(response: dict[str, Any]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    """(resource attributes, raw span) pairs from a ``/api/v3/traces`` response."""
    pairs: list[tuple[dict[str, Any], dict[str, Any]]] = []
    result = (response or {}).get("result") or {}
    for group in result.get("resourceSpans") or ():
        resource = attributes((group.get("resource") or {}).get("attributes"))
        for scope in group.get("scopeSpans") or ():
            pairs.extend((resource, span) for span in scope.get("spans") or ())
    return pairs


def service_spans(response: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(service.name, raw span) pairs."""
    return [(str(r.get("service.name") or ""), s) for r, s in resource_spans(response)]


def hex_id(value: Any, size: int) -> str:
    """Lowercase hex of ``size`` characters, from hex or base64; "" when absent or invalid."""
    if not value or not isinstance(value, str):
        return ""
    text = value.strip()
    if len(text) == size and all(c in "0123456789abcdefABCDEF" for c in text):
        return text.lower()
    try:
        raw = base64.b64decode(text, validate=True)
    except (binascii.Error, ValueError):
        return ""
    return raw.hex() if len(raw) * 2 == size else ""


def _kind(value: Any) -> SpanKind:
    number = (
        _KIND_NAMES.get(value, 0)
        if isinstance(value, str) and not value.isdigit()
        else int_value(value)
    )
    return KINDS.get(number or 0, "")


def _status(status: dict[str, Any], tags: dict[str, Any]) -> SpanStatus:
    raw = status.get("code")
    code = (
        _STATUS_NAMES.get(raw, 0)
        if isinstance(raw, str) and not raw.isdigit()
        else int_value(raw) or 0
    )
    if code == 2 or tags.get("error") in (True, "true", "True"):
        return "error"
    return "ok" if code == 1 else "unset"


def iso(nanos: int) -> str:
    return datetime.fromtimestamp(nanos / 1e9, tz=UTC).isoformat()


def _ms(nanos: int) -> float:
    return round(nanos / 1e6, 3)


def _depths(parents: dict[str, str | None]) -> dict[str, int]:
    depths: dict[str, int] = {}

    def depth(span_id: str) -> int:
        seen: list[str] = []
        current: str | None = span_id
        while current is not None and current not in depths and current not in seen:
            seen.append(current)
            parent = parents.get(current)
            current = parent if parent in parents else None
        base = depths.get(current, -1) if current is not None else -1
        for i, sid in enumerate(reversed(seen)):
            depths[sid] = base + 1 + i
        return depths[span_id]

    for span_id in parents:
        depth(span_id)
    return depths


def _trace(
    trace_id: str,
    raw: dict[str, tuple[dict[str, Any], dict[str, Any]]],
    max_spans: int,
) -> Trace:
    timed: list[tuple[str, dict[str, Any], dict[str, Any], int, int]] = []
    for span_id, (resource, span) in raw.items():
        start = int_value(span.get("startTimeUnixNano")) or 0
        end = max(int_value(span.get("endTimeUnixNano")) or start, start)
        timed.append((span_id, resource, span, start, end))
    trace_start = min(t[3] for t in timed)
    trace_end = max(t[4] for t in timed)
    parents: dict[str, str | None] = {}
    for span_id, _, span, _, _ in timed:
        parent = hex_id(span.get("parentSpanId"), 16)
        parents[span_id] = parent if parent and parent != span_id else None
    depths = _depths(parents)
    ordered = sorted(timed, key=lambda t: (t[3], depths[t[0]], t[0]))
    truncated = len(ordered) > max_spans
    ordered = ordered[:max_spans]
    kept = {t[0] for t in ordered}

    spans: list[Span] = []
    for span_id, resource, span, start, end in ordered:
        tags = flatten(attributes(span.get("attributes")))
        events = tuple(
            SpanEvent(
                name=str(event.get("name") or ""),
                offset_ms=_ms((int_value(event.get("timeUnixNano")) or start) - start),
                attributes=flatten(attributes(event.get("attributes"))),
            )
            for event in span.get("events") or ()
        )
        links = tuple(
            SpanLink(hex_id(link.get("traceId"), 32), hex_id(link.get("spanId"), 16))
            for link in span.get("links") or ()
        )
        parent_id = parents[span_id]
        status = span.get("status") or {}
        spans.append(
            Span(
                span_id=span_id,
                parent_id=parent_id if parent_id in kept else None,
                name=str(span.get("name") or ""),
                service=str(resource.get("service.name") or ""),
                kind=_kind(span.get("kind")),
                start_ms=_ms(start - trace_start),
                duration_ms=_ms(end - start),
                status=_status(status, tags),
                status_message=str(status.get("message") or ""),
                attributes=tags,
                resource=flatten(resource),
                events=events,
                links=links,
            )
        )
    return Trace(
        trace_id=trace_id,
        start=iso(trace_start),
        duration_ms=_ms(trace_end - trace_start),
        services=service_counts(spans),
        spans=tuple(spans),
        truncated=truncated,
    )


def to_traces(
    responses: dict[str, Any] | Iterable[dict[str, Any]], *, max_spans: int = MAX_SPANS
) -> list[Trace]:
    """Every trace in one or more responses; spans deduplicated by id."""
    if isinstance(responses, dict):
        responses = [responses]
    grouped: dict[str, dict[str, tuple[dict[str, Any], dict[str, Any]]]] = {}
    for response in responses:
        for resource, span in resource_spans(response):
            trace_id = hex_id(span.get("traceId"), 32)
            span_id = hex_id(span.get("spanId"), 16)
            if trace_id and span_id:
                grouped.setdefault(trace_id, {})[span_id] = (resource, span)
    return [_trace(trace_id, spans, max_spans) for trace_id, spans in grouped.items()]
