import pytest

pytest.importorskip("opentelemetry.sdk")

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from naas_abi.apps.nexus.apps.api.app.core import tracing  # noqa: E402
from opentelemetry.sdk.trace import TracerProvider  # noqa: E402
from opentelemetry.sdk.trace.export import SimpleSpanProcessor  # noqa: E402
from opentelemetry.sdk.trace.export.in_memory_span_exporter import (  # noqa: E402
    InMemorySpanExporter,
)
from opentelemetry.trace import SpanKind, StatusCode  # noqa: E402


@pytest.fixture
def spans(monkeypatch):
    exporter = InMemorySpanExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    monkeypatch.setattr(tracing, "_tracer", lambda: provider.get_tracer("test"))
    return exporter


def _client():
    app = FastAPI()

    @app.get("/api/items/{item_id}")
    async def item(item_id: str):
        return {"id": item_id}

    @app.get("/api/boom")
    async def boom():
        raise RuntimeError("boom")

    @app.get("/health")
    async def health():
        return {"status": "healthy"}

    app.add_middleware(tracing.TracingMiddleware)
    return TestClient(app, raise_server_exceptions=False)


def test_requests_get_a_server_span_named_after_the_route(spans):
    _client().get("/api/items/42")

    (span,) = spans.get_finished_spans()
    assert span.kind is SpanKind.SERVER
    assert span.name == "GET /api/items/{item_id}"
    assert span.attributes["http.response.status_code"] == 200
    assert span.attributes["http.route"] == "/api/items/{item_id}"


def test_an_incoming_traceparent_is_continued(spans):
    parent = "00-4bf92f3577b34da6a3ce929d0e0e4736-00f067aa0ba902b7-01"
    _client().get("/api/items/1", headers={"traceparent": parent})

    (span,) = spans.get_finished_spans()
    assert format(span.context.trace_id, "032x") == "4bf92f3577b34da6a3ce929d0e0e4736"


def test_server_errors_fail_the_span(spans):
    _client().get("/api/boom")

    (span,) = spans.get_finished_spans()
    assert span.status.status_code is StatusCode.ERROR


def test_health_checks_are_not_traced(spans):
    _client().get("/health")

    assert spans.get_finished_spans() == ()
