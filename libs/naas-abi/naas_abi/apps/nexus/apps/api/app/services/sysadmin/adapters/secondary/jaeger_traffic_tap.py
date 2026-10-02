"""Live traffic from traces: recent spans polled from Jaeger's query API (v3).

Each NATS call is one CLIENT span (transfers: one span with their totals), each
job run one CONSUMER span; the caller is the process (service.name) that
recorded the span. Server-side spans of the same calls are not listed again.
Spans arrive with the exporter's batch delay (about a second), so this view
trails the bus slightly. Responses are OTLP JSON (``resourceSpans``).
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
import time
from collections import OrderedDict
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traffic import TrafficEvent

logger = logging.getLogger(__name__)

SOURCE = "tracing"
KINDS_BY_SERVICE = {
    "model_registry": "model",
    "discovery": "discovery",
    "agent": "agent",
    "jobs": "job",
}
SPAN_KIND_CLIENT, SPAN_KIND_CONSUMER = 3, 5
STATUS_ERROR = 2
MAX_SEEN = 20_000


def _value(value: dict[str, Any]) -> Any:
    for key in ("stringValue", "boolValue", "doubleValue"):
        if key in value:
            return value[key]
    if "intValue" in value:
        return _int(value["intValue"])  # int64 travels as a string in OTLP JSON
    return None


def _attributes(items: Any) -> dict[str, Any]:
    return {item.get("key"): _value(item.get("value") or {}) for item in items or ()}


def _int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _event(span: dict[str, Any], caller: str) -> TrafficEvent | None:
    tags = _attributes(span.get("attributes"))
    kind = _int(span.get("kind"))
    start_ns = _int(span.get("startTimeUnixNano")) or 0
    end_ns = _int(span.get("endTimeUnixNano")) or start_ns
    failed = _int((span.get("status") or {}).get("code")) == STATUS_ERROR
    base = {
        "at": start_ns / 1e9,
        "caller": caller,
        "latency_ms": round((end_ns - start_ns) / 1e6, 3),
        "status": "error" if failed else "ok",
        "error_code": str(tags.get("abi.error_code") or ""),
        "trace_id": str(span.get("traceId", "")),
    }
    if kind == SPAN_KIND_CLIENT and tags.get("rpc.system") == "nats":
        service = str(tags.get("rpc.service") or "")
        operation = tags.get("abi.transfer.operation")
        if operation:
            return TrafficEvent(
                kind="transfer",
                subject=str(tags.get("messaging.destination.name") or ""),
                service=service,
                method=f"transfer.{operation}",
                request_bytes=_int(tags.get("abi.transfer.bytes_sent")) or 0,
                reply_bytes=_int(tags.get("abi.transfer.bytes_received")),
                **base,
            )
        return TrafficEvent(
            kind=KINDS_BY_SERVICE.get(service, "service"),
            subject=str(tags.get("messaging.destination.name") or ""),
            service=service,
            method=str(tags.get("rpc.method") or ""),
            request_bytes=_int(tags.get("messaging.message.body.size")) or 0,
            reply_bytes=_int(tags.get("abi.reply.body.size")),
            **base,
        )
    if kind == SPAN_KIND_CONSUMER and tags.get("abi.job.name"):
        return TrafficEvent(
            kind="job",
            subject=str(tags.get("messaging.destination.name") or ""),
            service=str(tags["abi.job.name"]),
            method="run",
            request_bytes=0,
            reply_bytes=None,
            **base,
        )
    return None


def _spans(response: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(service.name, span) pairs from a ``/api/v3/traces`` response."""
    pairs = []
    result = (response or {}).get("result") or {}
    for resource_spans in result.get("resourceSpans") or ():
        resource = _attributes((resource_spans.get("resource") or {}).get("attributes"))
        caller = str(resource.get("service.name") or "")
        for scope_spans in resource_spans.get("scopeSpans") or ():
            pairs.extend((caller, span) for span in scope_spans.get("spans") or ())
    return pairs


def span_events(response: dict[str, Any]) -> list[TrafficEvent]:
    """Traffic rows from a Jaeger ``/api/v3/traces`` response, oldest first."""
    events = [e for caller, span in _spans(response) if (e := _event(span, caller))]
    return sorted(events, key=lambda e: e.at)


def _rfc3339(seconds: float) -> str:
    return datetime.fromtimestamp(seconds, tz=UTC).isoformat().replace("+00:00", "Z")


def _default_client(base_url: str, timeout: float) -> Any:
    import httpx

    return httpx.AsyncClient(base_url=base_url, timeout=timeout)


class JaegerSpanTap:
    source = "traces"

    def __init__(
        self,
        query_url: str,
        *,
        poll_seconds: float = 2.0,
        lookback_seconds: float = 15.0,
        overlap_seconds: float = 10.0,
        limit: int = 200,
        timeout_seconds: float = 5.0,
        client_factory: Callable[[str, float], Any] = _default_client,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self._url = query_url.rstrip("/")
        self._poll = poll_seconds
        self._lookback = lookback_seconds
        self._overlap = overlap_seconds
        self._limit = limit
        self._timeout = timeout_seconds
        self._client_factory = client_factory
        self._clock = clock
        self._seen: OrderedDict[tuple[str, str], None] = OrderedDict()
        self._client: Any = None
        self._task: asyncio.Task | None = None
        self._cursor = 0.0
        self._emit: Callable[[TrafficEvent], None] = lambda event: None

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = await self._client.get(path, params=params)
        if response.status_code == 404 and path == "/api/v3/traces":
            return {}  # no trace in the window for this service
        response.raise_for_status()
        return response.json()

    async def _services(self) -> list[str]:
        body = await self._get("/api/v3/services")
        return [str(name) for name in (body or {}).get("services") or () if name != "jaeger"]

    async def start(self, emit: Callable[[TrafficEvent], None]) -> None:
        self._emit = emit
        self._client = self._client_factory(self._url, self._timeout)
        try:
            await self._services()
        except Exception as exc:  # noqa: BLE001 - unreachable, refused, not Jaeger
            await self.stop()
            raise SourceUnavailable(SOURCE, str(exc) or type(exc).__name__) from exc
        self._cursor = self._clock() - self._lookback
        self._task = asyncio.create_task(self._loop())

    async def stop(self) -> None:
        if self._task is not None:
            self._task.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None
        if self._client is not None:
            with contextlib.suppress(Exception):
                await self._client.aclose()
            self._client = None

    async def _loop(self) -> None:
        while True:
            try:
                await self.poll_once()
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 - keep polling through Jaeger hiccups
                logger.warning("Polling Jaeger for live traffic failed", exc_info=True)
            await asyncio.sleep(self._poll)

    async def poll_once(self) -> None:
        end = self._clock()
        start = self._cursor - self._overlap  # spans arrive after their batch delay
        fresh: list[TrafficEvent] = []
        for service in await self._services():
            body = await self._get(
                "/api/v3/traces",
                {
                    "query.service_name": service,
                    "query.start_time_min": _rfc3339(start),
                    "query.start_time_max": _rfc3339(end),
                    "query.search_depth": self._limit,
                },
            )
            for caller, span in _spans(body):
                key = (str(span.get("traceId")), str(span.get("spanId")))
                if key in self._seen:
                    continue
                self._seen[key] = None
                event = _event(span, caller)
                if event is not None:
                    fresh.append(event)
        while len(self._seen) > MAX_SEEN:
            self._seen.popitem(last=False)
        for event in sorted(fresh, key=lambda e: e.at):
            self._emit(event)
        self._cursor = end
