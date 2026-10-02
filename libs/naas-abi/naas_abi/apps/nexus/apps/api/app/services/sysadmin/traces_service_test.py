import asyncio
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_traces import (
    InMemoryTraceStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    InvalidTraceQuery,
    TraceNotFound,
    TraceQuery,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces_service import TraceService

NOW = datetime(2026, 10, 2, 9, 0, 0, tzinfo=UTC)


def run(coro):
    return asyncio.run(coro)


def _service(**kwargs):
    store = InMemoryTraceStore(fixtures.traces(NOW), clock=lambda: NOW)
    return TraceService(store, **kwargs), store


def test_services_operations_and_the_backend_ui():
    service, _ = _service(ui_url="http://jaeger:16686/")

    assert run(service.services()) == ["nexus-api", "ops-researcher", "zen-engine"]
    assert run(service.operations("zen-engine")) == [("document/get", "client")]
    with pytest.raises(InvalidTraceQuery):
        run(service.operations(""))
    assert service.ui_url == "http://jaeger:16686"
    assert TraceService(SourceUnavailable("tracing", "off")).ui_url is None


def test_search_validates_the_query():
    service, store = _service()

    found = run(service.search(TraceQuery(errors=True)))

    assert [s.trace_id for s in found] == [fixtures.TRACE_B]
    assert store.searches == [TraceQuery(errors=True)]
    for bad in (
        TraceQuery(lookback="2h"),
        TraceQuery(limit=0),
        TraceQuery(limit=101),
        TraceQuery(min_duration_ms=-1),
        TraceQuery(min_duration_ms=10, max_duration_ms=5),
    ):
        with pytest.raises(InvalidTraceQuery):
            run(service.search(bad))
    assert len(store.searches) == 1


def test_get_normalizes_the_id():
    service, _ = _service()

    trace = run(service.get(fixtures.TRACE_A.upper()))

    assert trace.trace_id == fixtures.TRACE_A
    with pytest.raises(TraceNotFound) as exc:
        run(service.get("0" * 32))
    assert str(exc.value) == f"trace {'0' * 32} not found"
    for bad in ("xyz", "0" * 31, "0" * 33, "g" * 32):
        with pytest.raises(InvalidTraceQuery):
            run(service.get(bad))


def test_without_tracing_every_use_case_is_unavailable():
    off = SourceUnavailable("tracing", "telemetry is not enabled (telemetry.query_url)")
    service = TraceService(off)

    for call in (
        service.services,
        lambda: service.operations("x"),
        lambda: service.search(TraceQuery()),
        lambda: service.get("0" * 32),
        lambda: service.operations(""),
        lambda: service.search(TraceQuery(limit=0)),
        lambda: service.get("not an id"),
    ):
        with pytest.raises(SourceUnavailable) as exc:
            run(call())
        assert exc.value is off
