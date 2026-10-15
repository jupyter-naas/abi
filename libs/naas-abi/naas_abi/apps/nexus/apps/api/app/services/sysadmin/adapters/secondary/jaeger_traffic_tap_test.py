import asyncio

import httpx
import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_traffic_tap import (
    JaegerSpanTap,
    span_events,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable

TRACE_ID = "4bf92f3577b34da6a3ce929d0e0e4736"
T0 = 1_759_392_000_000_000_000  # ns


def _attrs(**values):
    out = []
    for key, value in values.items():
        if isinstance(value, bool):
            out.append({"key": key, "value": {"boolValue": value}})
        elif isinstance(value, int):
            out.append(
                {"key": key, "value": {"intValue": str(value)}}
            )  # OTLP JSON: int64 as string
        else:
            out.append({"key": key, "value": {"stringValue": value}})
    return out


def _span(span_id, name, kind, start_ns, duration_ns, error=False, **attributes):
    span = {
        "traceId": TRACE_ID,
        "spanId": span_id,
        "name": name,
        "kind": kind,
        "startTimeUnixNano": str(start_ns),
        "endTimeUnixNano": str(start_ns + duration_ns),
        "attributes": _attrs(**attributes),
        "status": {"code": 2, "message": "boom"} if error else {},
    }
    return span


def _resource(service, *spans):
    return {
        "resource": {"attributes": _attrs(**{"service.name": service})},
        "scopeSpans": [{"scope": {"name": "naas_abi"}, "spans": list(spans)}],
    }


CLIENT, SERVER, CONSUMER = 3, 2, 5
NATS = {"rpc.system": "nats", "messaging.system": "nats"}

RESPONSE = {
    "result": {
        "resourceSpans": [
            _resource(
                "zen-engine",
                _span(
                    "a1",
                    "document/get",
                    CLIENT,
                    T0,
                    1_500_000,
                    **NATS,
                    **{
                        "rpc.service": "document",
                        "rpc.method": "get",
                        "messaging.destination.name": "abi.svc.document.v1.get",
                        "messaging.message.body.size": 12,
                        "abi.reply.body.size": 340,
                    },
                ),
                _span(
                    "a2",
                    "object_storage/transfer.put",
                    CLIENT,
                    T0 + 100_000_000,
                    14_000_000,
                    **NATS,
                    **{
                        "rpc.service": "object_storage",
                        "rpc.method": "transfer",
                        "abi.transfer.operation": "put",
                        "abi.transfer.bytes_sent": 300000,
                        "abi.transfer.bytes_received": 64,
                        "abi.transfer.messages": 8,
                    },
                ),
                _span("a4", "document/get", SERVER, T0 + 100, 1_000_000, **NATS),
            ),
            _resource(
                "ops.researcher",
                _span(
                    "a3",
                    "keyvalue/get",
                    CLIENT,
                    T0 + 200_000_000,
                    900_000,
                    error=True,
                    **NATS,
                    **{
                        "rpc.service": "keyvalue",
                        "rpc.method": "get",
                        "abi.error_code": "KV_NOT_FOUND",
                    },
                ),
                _span(
                    "a5",
                    "job digest",
                    CONSUMER,
                    T0 + 300_000_000,
                    250_000_000,
                    **{"abi.job.name": "digest", "abi.module.id": "ops.researcher"},
                ),
            ),
        ]
    }
}


def test_spans_become_traffic_rows():
    events = {(e.service, e.method): e for e in span_events(RESPONSE)}

    get = events[("document", "get")]
    assert (get.kind, get.caller, get.request_bytes, get.reply_bytes) == (
        "service",
        "zen-engine",
        12,
        340,
    )
    assert (get.latency_ms, get.status, get.trace_id) == (1.5, "ok", TRACE_ID)
    assert get.subject == "abi.svc.document.v1.get" and get.at == pytest.approx(1_759_392_000.0)

    put = events[("object_storage", "transfer.put")]
    assert (put.kind, put.request_bytes, put.reply_bytes, put.latency_ms) == (
        "transfer",
        300000,
        64,
        14.0,
    )

    failed = events[("keyvalue", "get")]
    assert (failed.status, failed.error_code, failed.caller) == (
        "error",
        "KV_NOT_FOUND",
        "ops.researcher",
    )

    job = events[("digest", "run")]
    assert (job.kind, job.caller, job.latency_ms) == ("job", "ops.researcher", 250.0)

    assert len(span_events(RESPONSE)) == 4  # the server span of document/get is not listed again


def _client(requests, *, services=("zen-engine", "ops.researcher"), fail=False, empty=()):
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if fail:
            raise httpx.ConnectError("refused")
        if request.url.path == "/api/v3/services":
            return httpx.Response(200, json={"services": list(services)})
        if request.url.params.get("query.service_name") in empty:
            return httpx.Response(404, json={"error": {"code": 5, "message": "trace not found"}})
        return httpx.Response(200, json=RESPONSE)

    def factory(base_url, timeout):
        return httpx.AsyncClient(base_url=base_url, transport=httpx.MockTransport(handler))

    return factory


def test_the_tap_polls_every_service_and_emits_each_span_once():
    requests, seen = [], []

    async def scenario():
        tap = JaegerSpanTap(
            "http://jaeger:16686", poll_seconds=0.01, client_factory=_client(requests)
        )
        await tap.start(seen.append)
        await asyncio.sleep(0.1)
        await tap.stop()

    asyncio.run(scenario())

    assert len(seen) == 4  # same spans returned for both services and every poll: once each
    queried = {
        r.url.params.get("query.service_name") for r in requests if r.url.path == "/api/v3/traces"
    }
    assert queried == {"zen-engine", "ops.researcher"}
    trace_query = next(r for r in requests if r.url.path == "/api/v3/traces")
    assert trace_query.url.params["query.start_time_min"].endswith("Z")


def test_services_without_recent_traces_are_not_errors():
    requests, seen = [], []

    async def scenario():
        tap = JaegerSpanTap(
            "http://jaeger:16686",
            poll_seconds=0.01,
            client_factory=_client(requests, empty=("zen-engine",)),
        )
        await tap.start(seen.append)
        await asyncio.sleep(0.05)
        await tap.stop()

    asyncio.run(scenario())

    assert len(seen) == 4  # from ops.researcher's query


def test_an_unreachable_jaeger_is_unavailable():
    async def scenario():
        await JaegerSpanTap("http://jaeger:16686", client_factory=_client([], fail=True)).start(
            lambda e: None
        )

    with pytest.raises(SourceUnavailable) as raised:
        asyncio.run(scenario())
    assert raised.value.source == "tracing"
