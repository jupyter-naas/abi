from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.primary.sysadmin__primary_adapter__FastAPI import (
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_traces import (
    InMemoryTraceStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import (
    TRACING_OFF,
    get_trace_store,
    get_trace_ui_url,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import TraceQuery

BASE = "/api/admin/system/traces"
NOW = datetime(2026, 10, 2, 9, 0, 0, tzinfo=UTC)
A, B = fixtures.TRACE_A, fixtures.TRACE_B
ROUTES = ["/services", "/operations?service=nexus-api", "", f"/{A}"]

SUMMARY_KEYS = {"trace_id", "root", "start", "duration_ms", "spans", "errors", "services"}
SPAN_KEYS = {
    "span_id",
    "parent_id",
    "name",
    "service",
    "kind",
    "start_ms",
    "duration_ms",
    "status",
    "status_message",
    "attributes",
    "resource",
    "events",
    "links",
}


def _client(store, *, is_superadmin=True, ui_url="http://localhost:16686"):
    app = FastAPI()
    app.include_router(router, prefix="/api/admin/system")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u1@example.com", name="U1", is_superadmin=is_superadmin
    )
    app.dependency_overrides[get_trace_store] = lambda: store
    app.dependency_overrides[get_trace_ui_url] = lambda: ui_url
    return TestClient(app)


@pytest.fixture
def store():
    return InMemoryTraceStore(fixtures.traces(NOW), clock=lambda: NOW)


@pytest.fixture
def client(store):
    return _client(store)


@pytest.mark.parametrize("path", ROUTES)
def test_every_route_is_for_super_admins_only(store, path):
    assert _client(store, is_superadmin=False).get(BASE + path).status_code == 403


@pytest.mark.parametrize("path", [*ROUTES, "/not-a-trace-id", "/operations"])
def test_every_route_answers_503_when_tracing_is_off(path):
    client = _client(SourceUnavailable("tracing", TRACING_OFF), ui_url=None)

    response = client.get(BASE + path)

    assert response.status_code == 503
    assert response.json() == {
        "detail": {"source": "tracing", "reason": "telemetry is not enabled (telemetry.query_url)"}
    }


def test_a_backend_that_cannot_answer_is_503():
    response = _client(InMemoryTraceStore(fail="jaeger at http://jaeger:16686: refused")).get(
        BASE + "/services"
    )

    assert response.status_code == 503
    assert response.json()["detail"] == {
        "source": "tracing",
        "reason": "jaeger at http://jaeger:16686: refused",
    }


def test_services_with_the_backend_ui(client):
    assert client.get(BASE + "/services").json() == {
        "services": ["nexus-api", "ops-researcher", "zen-engine"],
        "ui_url": "http://localhost:16686",
    }
    assert _client(InMemoryTraceStore(), ui_url=None).get(BASE + "/services").json() == {
        "services": [],
        "ui_url": None,
    }


def test_operations_of_a_service(client):
    assert client.get(BASE + "/operations", params={"service": "ops-researcher"}).json() == {
        "operations": [
            {"name": "digest", "kind": "consumer"},
            {"name": "fetch", "kind": "internal"},
        ]
    }
    missing = client.get(BASE + "/operations")
    assert missing.status_code == 400
    assert missing.json()["detail"] == {"source": "tracing", "reason": "service is required"}


def test_search_shape_newest_first(client):
    body = client.get(BASE).json()

    assert [t["trace_id"] for t in body["traces"]] == [B, A]
    newest, older = body["traces"]
    assert set(newest) == SUMMARY_KEYS
    assert newest == {
        "trace_id": B,
        "root": {"service": "ops-researcher", "name": "digest"},
        "start": "2026-10-02T08:59:00+00:00",
        "duration_ms": 1500.0,
        "spans": 2,
        "errors": 1,
        "services": [{"name": "ops-researcher", "spans": 2, "errors": 1}],
    }
    assert older["services"] == [
        {"name": "nexus-api", "spans": 1, "errors": 0},
        {"name": "zen-engine", "spans": 1, "errors": 0},
    ]


def test_search_parameters_reach_the_store(client, store):
    def ids(**params):
        response = client.get(BASE, params=params)
        assert response.status_code == 200, response.text
        return [t["trace_id"] for t in response.json()["traces"]]

    assert ids(service="zen-engine") == [A]
    assert ids(operation="fetch") == [B]
    assert ids(errors="true") == [B] and ids(errors="false") == [B, A]
    assert ids(min_duration_ms=1000) == [B]
    assert ids(max_duration_ms="999.5") == [A]
    assert ids(lookback="6h") == [B, A, fixtures.TRACE_C]
    assert ids(limit=1) == [B]
    assert ids(service="", operation="") == [B, A]
    assert store.searches[0] == TraceQuery(service="zen-engine")
    assert store.searches[-1] == TraceQuery()


@pytest.mark.parametrize(
    "params",
    [
        {"lookback": "2h"},
        {"limit": 0},
        {"limit": 101},
        {"min_duration_ms": -1},
        {"min_duration_ms": 10, "max_duration_ms": 5},
    ],
)
def test_malformed_searches_are_400(client, store, params):
    response = client.get(BASE, params=params)

    assert response.status_code == 400
    assert response.json()["detail"]["source"] == "tracing"
    assert response.json()["detail"]["reason"]
    assert store.searches == []


def test_a_whole_trace(client):
    body = client.get(f"{BASE}/{B}").json()

    assert set(body) == {"trace_id", "start", "duration_ms", "services", "spans", "truncated"}
    assert (body["trace_id"], body["start"], body["duration_ms"], body["truncated"]) == (
        B,
        "2026-10-02T08:59:00+00:00",
        1500.0,
        False,
    )
    digest, fetch = body["spans"]
    assert set(digest) == SPAN_KEYS
    assert digest == {
        "span_id": "b000000000000001",
        "parent_id": None,
        "name": "digest",
        "service": "ops-researcher",
        "kind": "consumer",
        "start_ms": 0.0,
        "duration_ms": 1500.0,
        "status": "unset",
        "status_message": "",
        "attributes": {},
        "resource": {"service.name": "ops-researcher"},
        "events": [],
        "links": [],
    }
    assert (fetch["parent_id"], fetch["status"], fetch["status_message"]) == (
        "b000000000000001",
        "error",
        "boom",
    )
    assert fetch["events"] == [{"name": "retry", "offset_ms": 50.0, "attributes": {"attempt": 2}}]


def test_trace_ids_are_case_insensitive(client):
    body = client.get(f"{BASE}/{A.upper()}").json()

    assert body["trace_id"] == A
    assert body["spans"][1]["attributes"] == {"rpc.service": "document"}


def test_unknown_traces_are_404(client):
    response = client.get(f"{BASE}/{'0' * 32}")

    assert response.status_code == 404
    assert response.json() == {
        "detail": {"source": "tracing", "reason": f"trace {'0' * 32} not found"}
    }


@pytest.mark.parametrize("trace_id", ["xyz", "0" * 31, "0" * 33, "g" * 32])
def test_malformed_trace_ids_are_400(client, trace_id):
    response = client.get(f"{BASE}/{trace_id}")

    assert response.status_code == 400
    assert response.json()["detail"]["source"] == "tracing"
