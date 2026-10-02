"""The trace store against a real Jaeger v2 (skipped without the `jaeger` binary).

The OpenTelemetry SDK records ``fixtures.traces`` (A, B and C) with explicit
times, one tracer provider per service, and exports them over OTLP HTTP.
"""

import asyncio
import time

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_trace_store import (
    JaegerTraceStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.jaeger_traffic_tap_integration_test import (
    run_jaeger,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import TraceStoreContract

pytestmark = pytest.mark.integration

MS = 1_000_000  # ns


def _record(otlp_url):
    """Exports the contract's traces; returns their ids as {"a", "b", "c"}."""
    from opentelemetry import trace
    from opentelemetry.context import Context
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor
    from opentelemetry.trace import SpanKind, Status, StatusCode

    providers = []

    def tracer(service):
        provider = TracerProvider(resource=Resource.create({"service.name": service}))
        provider.add_span_processor(
            SimpleSpanProcessor(OTLPSpanExporter(endpoint=f"{otlp_url}/v1/traces"))
        )
        providers.append(provider)
        return provider.get_tracer("itest")

    api, engine, researcher = tracer("nexus-api"), tracer("zen-engine"), tracer("ops-researcher")
    now = time.time_ns()

    def root(tracer_, name, kind, start):
        return tracer_.start_span(name, context=Context(), kind=kind, start_time=start)

    def child(tracer_, parent, name, kind, start, **attributes):
        return tracer_.start_span(
            name,
            context=trace.set_span_in_context(parent),
            kind=kind,
            start_time=start,
            attributes=attributes,
        )

    a0 = now - 120_000 * MS
    search = root(api, "GET /api/search", SpanKind.SERVER, a0)
    search.set_attribute("http.request.method", "GET")
    get = child(
        engine, search, "document/get", SpanKind.CLIENT, a0 + 10 * MS, **{"rpc.service": "document"}
    )
    get.set_status(Status(StatusCode.OK))
    get.end(end_time=a0 + 210 * MS)
    search.end(end_time=a0 + 250 * MS)

    b0 = now - 60_000 * MS
    digest = root(researcher, "digest", SpanKind.CONSUMER, b0)
    fetch = child(researcher, digest, "fetch", SpanKind.INTERNAL, b0 + 100 * MS)
    fetch.add_event("retry", {"attempt": 2}, timestamp=b0 + 150 * MS)
    fetch.set_status(Status(StatusCode.ERROR, "boom"))
    fetch.end(end_time=b0 + 500 * MS)
    digest.end(end_time=b0 + 1500 * MS)

    c0 = now - 7_200_000 * MS
    health = root(api, "GET /health", SpanKind.SERVER, c0)
    health.end(end_time=c0 + 5 * MS)

    for provider in providers:
        provider.force_flush()
        provider.shutdown()
    return {
        name: format(span.get_span_context().trace_id, "032x")
        for name, span in (("a", search), ("b", digest), ("c", health))
    }


@pytest.fixture(scope="module")
def deployment(tmp_path_factory):
    with run_jaeger(tmp_path_factory.mktemp("jaeger")) as (query_url, otlp_url):
        ids = _record(otlp_url)
        store = JaegerTraceStore(query_url)

        async def stored():
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                found = [await store.get(trace_id) for trace_id in ids.values()]
                if [len(t.spans) if t else 0 for t in found] == [2, 2, 1]:
                    return
                await asyncio.sleep(0.2)
            raise AssertionError("jaeger did not store the traces in time")

        asyncio.run(stored())
        yield store, ids


class TestJaegerTraceStore(TraceStoreContract):
    @pytest.fixture
    def store(self, deployment):
        return deployment[0]

    @pytest.fixture
    def trace_ids(self, deployment):
        return deployment[1]

    def test_ids_are_accepted_in_any_case(self, store, trace_ids):
        trace = asyncio.run(store.get(trace_ids["a"].upper()))

        assert trace is not None and trace.trace_id == trace_ids["a"]
