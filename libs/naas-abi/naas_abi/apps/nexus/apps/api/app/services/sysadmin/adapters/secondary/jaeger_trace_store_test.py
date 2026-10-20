import asyncio
import socket

import httpx
import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_trace_store import (
    JaegerTraceStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import (
    UnavailableTraceStoreContract,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import TraceQuery

NOW = 1_759_392_060.0  # 60 s after fixtures.T0_NS


def run(coro):
    return asyncio.run(coro)


class Jaeger:
    """A scripted query API: ``routes`` maps a path to a JSON body or a status."""

    def __init__(self, routes=None, *, services=("nexus-api", "zen-engine", "jaeger")):
        self.routes = {"/api/v3/services": {"services": list(services)}, **(routes or {})}
        self.requests = []
        self.closed = 0

    def handler(self, request):
        self.requests.append(request)
        key = request.url.path
        if key == "/api/v3/traces":
            key = f"{key}?{request.url.params.get('query.service_name')}"
        answer = self.routes.get(key, 404)
        if isinstance(answer, Exception):
            raise answer
        if isinstance(answer, int):
            return httpx.Response(answer, json={"error": {"message": "not found"}})
        if isinstance(answer, str):
            return httpx.Response(200, text=answer)
        return httpx.Response(200, json=answer)

    def store(self, **kwargs):
        jaeger = self

        class Client(httpx.AsyncClient):
            async def aclose(self):
                jaeger.closed += 1
                await super().aclose()

        def factory(base_url, timeout):
            return Client(base_url=base_url, transport=httpx.MockTransport(self.handler))

        return JaegerTraceStore(
            "http://jaeger:16686/", client_factory=factory, clock=lambda: NOW, **kwargs
        )

    def searched(self):
        return [r.url.params for r in self.requests if r.url.path == "/api/v3/traces"]


def _response(*spans, service="zen-engine"):
    return {"result": {"resourceSpans": [fixtures.otlp_resource(service, *spans)]}}


def test_services_are_sorted_without_jaeger_itself():
    jaeger = Jaeger(services=("zen-engine", "jaeger", "nexus-api", "zen-engine"))

    assert run(jaeger.store().services()) == ["nexus-api", "zen-engine"]
    assert jaeger.closed == 1


def test_operations_with_their_kinds():
    operations = [
        {"name": "GET /", "spanKind": "server"},
        {"name": "GET /", "spanKind": "server"},
        {"name": "send", "spanKind": "SPAN_KIND_PRODUCER"},
        {"name": "work", "spanKind": ""},
        {"name": "odd", "spanKind": "unspecified"},
        {"name": "", "spanKind": "client"},
    ]
    jaeger = Jaeger({"/api/v3/operations": {"operations": operations}})

    assert run(jaeger.store().operations("nexus-api")) == [
        ("GET /", "server"),
        ("odd", ""),
        ("send", "producer"),
        ("work", ""),
    ]
    assert jaeger.requests[-1].url.params["service"] == "nexus-api"
    assert run(Jaeger().store().operations("nope")) == []


def test_search_asks_each_service_and_merges_by_trace():
    root = fixtures.otlp_span("a" * 32, "1" * 16, "GET /", kind=2, duration_ms=50)
    child = fixtures.otlp_span("a" * 32, "2" * 16, "get", parent="1" * 16, start_ms=5)
    newer = fixtures.otlp_span("b" * 32, "3" * 16, "tick", start_ms=1000)
    jaeger = Jaeger(
        {
            "/api/v3/traces?nexus-api": _response(root, child, service="nexus-api"),
            "/api/v3/traces?zen-engine": _response(child, newer),
        }
    )

    found = run(jaeger.store().search(TraceQuery(lookback="15m", operation="get")))

    assert [(s.trace_id, s.spans) for s in found] == [("b" * 32, 1), ("a" * 32, 2)]
    assert [p["query.service_name"] for p in jaeger.searched()] == ["nexus-api", "zen-engine"]
    params = jaeger.searched()[0]
    assert params["query.start_time_min"] == "2025-10-02T07:46:00Z"
    assert params["query.start_time_max"] == "2025-10-02T08:01:00Z"
    assert params["query.operation_name"] == "get"
    assert params["query.search_depth"] == "20"
    assert jaeger.closed == 1


def test_search_of_one_service_and_no_match():
    jaeger = Jaeger()

    assert run(jaeger.store().search(TraceQuery(service="zen-engine", limit=5))) == []
    assert [r.url.path for r in jaeger.requests] == ["/api/v3/traces"]
    assert jaeger.searched()[0]["query.search_depth"] == "5"
    assert "query.operation_name" not in jaeger.searched()[0]


def test_trace_level_filters_search_deeper_and_run_here():
    ok = fixtures.otlp_span("a" * 32, "1" * 16, "ok", duration_ms=10)
    failed = fixtures.otlp_span("b" * 32, "2" * 16, "failed", status={"code": 2})
    jaeger = Jaeger({"/api/v3/traces?zen-engine": _response(ok, failed)})

    found = run(jaeger.store().search(TraceQuery(service="zen-engine", errors=True, limit=30)))

    assert [s.trace_id for s in found] == ["b" * 32]
    assert jaeger.searched()[0]["query.search_depth"] == "150"
    run(jaeger.store().search(TraceQuery(service="zen-engine", min_duration_ms=1, limit=100)))
    assert jaeger.searched()[-1]["query.search_depth"] == "500"


def test_search_without_a_service_is_capped_and_limited():
    services = [f"svc-{i:02d}" for i in range(30)]
    routes = {
        f"/api/v3/traces?{name}": _response(
            fixtures.otlp_span(f"{i + 1:032x}", f"{i + 1:016x}", "op", start_ms=i), service=name
        )
        for i, name in enumerate(services)
    }
    jaeger = Jaeger(routes, services=services)

    found = run(jaeger.store(max_services=25).search(TraceQuery(limit=3)))

    assert len(jaeger.searched()) == 25
    assert [s.root.service for s in found] == ["svc-24", "svc-23", "svc-22"]


def test_gets_a_trace_by_its_lowercase_id():
    jaeger = Jaeger({f"/api/v3/traces/{fixtures.OTLP_TRACE}": fixtures.otlp_response()})

    trace = run(jaeger.store().get(fixtures.OTLP_TRACE.upper()))

    assert trace is not None and len(trace.spans) == 4
    assert run(jaeger.store().get("0" * 32)) is None
    assert run(jaeger.store(max_spans=2).get(fixtures.OTLP_TRACE)).truncated


@pytest.mark.parametrize(
    "answer",
    [httpx.ConnectError("connection refused"), 500, "<html>not jaeger</html>"],
)
def test_jaeger_that_cannot_answer_is_unavailable(answer):
    jaeger = Jaeger({"/api/v3/services": answer})

    with pytest.raises(SourceUnavailable) as exc:
        run(jaeger.store().services())

    assert exc.value.source == "tracing" and exc.value.reason
    assert jaeger.closed == 1


def _closed_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class TestUnreachableJaegerTraceStore(UnavailableTraceStoreContract):
    @pytest.fixture
    def store(self):
        return JaegerTraceStore(f"http://127.0.0.1:{_closed_port()}", timeout_seconds=1.0)
