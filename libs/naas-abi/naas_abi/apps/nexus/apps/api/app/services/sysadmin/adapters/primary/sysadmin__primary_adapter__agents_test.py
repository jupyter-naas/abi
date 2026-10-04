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
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory import (
    InMemoryModuleRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_agents import (
    InMemoryAgentControl,
    InMemoryAgentRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.agents_service import AgentsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_agents_admin
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import (
    RemoteModuleInstance,
    SourceUnavailable,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

BASE = "/api/admin/system/agents"
RUN_KEYS = {
    "key",
    "module_id",
    "run_id",
    "agent",
    "invocation_id",
    "status",
    "thread_id",
    "caller",
    "owner",
    "submitted_at",
    "finished_at",
    "duration_ms",
    "error_code",
    "error_message",
    "trace_id",
    "events",
}


def _admin(control, audit, **overrides):
    parts = {
        "registry": InMemoryModuleRegistry(
            [
                RemoteModuleInstance(
                    "acme.agents", "i-1", "0.1.0", 1, "READY", 1.9e9, ("Researcher",)
                ),
                RemoteModuleInstance("acme.other", "w-1", "0.1.0", 1, "READY", 1.9e9, ("Writer",)),
            ]
        ),
        "runs": InMemoryAgentRunStore(fixtures.agent_runs(), fixtures.agent_events()),
        "control": control,
        "audit": audit,
        "trace_ui_url": "http://jaeger:16686/",
    }
    parts.update(overrides)
    return AgentsAdminService(**parts)


def _client(admin, *, is_superadmin=True):
    app = FastAPI()
    app.include_router(router, prefix="/api/admin/system")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u1@example.com", name="U1", is_superadmin=is_superadmin
    )
    app.dependency_overrides[get_agents_admin] = lambda: admin
    return TestClient(app)


@pytest.fixture
def control():
    return InMemoryAgentControl()


@pytest.fixture
def audit():
    return InMemoryAuditLog()


@pytest.fixture
def client(control, audit):
    return _client(_admin(control, audit))


@pytest.mark.parametrize(
    "method,path",
    [("GET", "/runs"), ("GET", "/runs/acme.agents/r2"), ("POST", "/runs/acme.agents/r4/cancel")],
)
def test_every_route_is_for_super_admins_only(control, audit, method, path):
    client = _client(_admin(control, audit), is_superadmin=False)

    assert client.request(method, BASE + path).status_code == 403
    assert control.cancelled == []


def test_runs_page(client):
    body = client.get(f"{BASE}/runs", params={"limit": 2}).json()

    assert [r["run_id"] for r in body["runs"]] == ["r4", "r3"]
    assert set(body["runs"][0]) == RUN_KEYS
    assert body["next"] == "2026-10-02T10:00:00+00:00"
    rest = client.get(f"{BASE}/runs", params={"before": body["next"]}).json()
    assert [r["run_id"] for r in rest["runs"]] == ["r2", "r1"] and rest["next"] is None
    failed = client.get(f"{BASE}/runs", params={"status": "failed, cancelled"}).json()
    assert [r["run_id"] for r in failed["runs"]] == ["r3", "r1"]
    assert [
        r["run_id"]
        for r in client.get(f"{BASE}/runs", params={"module": "acme.other"}).json()["runs"]
    ] == ["r3"]


def test_run_detail_has_events_and_trace_link(client):
    body = client.get(f"{BASE}/runs/acme.agents/r2").json()

    assert set(body) == RUN_KEYS | {"event_list", "trace_url"}
    assert body["duration_ms"] == 12500
    assert [e["event"] for e in body["event_list"]] == ["message", "message", "done"]
    assert body["event_list"][1]["truncated"] is True
    assert body["trace_url"] == f"http://jaeger:16686/trace/{'c' * 32}"
    assert client.get(f"{BASE}/runs/acme.agents/r99").status_code == 404


def test_cancel_is_audited_and_refused_for_finished_runs(client, control, audit):
    assert client.post(f"{BASE}/runs/acme.agents/r4/cancel").status_code == 202
    assert control.cancelled == ["acme.agents/r4"]
    assert [r.phase for r in audit.records] == ["requested", "succeeded"]
    assert audit.records[0].action.actor_id == "u1"

    refused = client.post(f"{BASE}/runs/acme.agents/r2/cancel")
    assert refused.status_code == 409


def test_unavailable_sources_and_audit_answer_503(control):
    down = _client(
        _admin(control, InMemoryAuditLog(), runs=SourceUnavailable("agent_runs", "no documents"))
    )
    response = down.get(f"{BASE}/runs")
    assert response.status_code == 503
    assert response.json()["detail"] == {"source": "agent_runs", "reason": "no documents"}

    no_audit = _client(_admin(control, InMemoryAuditLog(fail="db down")))
    response = no_audit.post(f"{BASE}/runs/acme.agents/r4/cancel")
    assert response.status_code == 503 and response.json()["detail"]["source"] == "audit"
    assert control.cancelled == []
