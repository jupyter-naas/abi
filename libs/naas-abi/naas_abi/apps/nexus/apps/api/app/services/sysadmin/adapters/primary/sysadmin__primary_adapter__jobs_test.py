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
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_jobs import (
    InMemoryJobCatalog,
    InMemoryJobControl,
    InMemoryJobQueue,
    InMemoryJobRunStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.factory import get_jobs_admin
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures

BASE = "/api/admin/system/jobs"
NOW = datetime(2026, 10, 2, 9, 5, 0, tzinfo=UTC)

RUN_KEYS = {
    "key",
    "module_id",
    "job",
    "run_id",
    "status",
    "attempt",
    "max_attempts",
    "trigger",
    "fired_at",
    "started_at",
    "finished_at",
    "duration_ms",
    "instance",
    "error",
    "trace_id",
}


@pytest.fixture
def control():
    return InMemoryJobControl()


@pytest.fixture
def audit():
    return InMemoryAuditLog()


def _admin(control, audit, **overrides):
    parts = {
        "catalogs": [InMemoryJobCatalog(fixtures.job_definitions())],
        "runs": InMemoryJobRunStore(fixtures.job_runs()),
        "control": control,
        "queue": InMemoryJobQueue({("acme.jobs", "nightly"): (2, 1)}),
        "audit": audit,
        "project": "zen",
        "trace_ui_url": "http://jaeger:16686/",
        "clock": lambda: NOW,
    }
    parts.update(overrides)
    return JobsAdminService(**parts)


def _client(admin, *, is_superadmin=True):
    app = FastAPI()
    app.include_router(router, prefix="/api/admin/system")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="u1", email="u1@example.com", name="U1", is_superadmin=is_superadmin
    )
    app.dependency_overrides[get_jobs_admin] = lambda: admin
    return TestClient(app)


@pytest.fixture
def client(control, audit):
    return _client(_admin(control, audit))


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", ""),
        ("GET", "/runs"),
        ("GET", "/failures"),
        ("GET", "/runs/acme.jobs/nightly:3"),
        ("POST", "/runs/acme.jobs/sync:9/cancel"),
        ("POST", "/acme.jobs/nightly/trigger"),
    ],
)
def test_every_route_is_for_super_admins_only(control, audit, method, path):
    client = _client(_admin(control, audit), is_superadmin=False)

    assert client.request(method, BASE + path).status_code == 403
    assert control.triggered == [] and control.cancelled == []


def test_overview_shape(client):
    body = client.get(BASE).json()
    jobs = {j["key"]: j for j in body["jobs"]}
    nightly = jobs["acme.jobs/nightly"]

    assert body["project"] == "zen"
    assert set(body["sources"]) == {"engine", "runs", "queue"}
    assert body["sources"]["runs"] == {"available": True, "reason": ""}
    assert set(nightly) == {
        "key",
        "module_id",
        "name",
        "description",
        "location",
        "instances",
        "triggers",
        "next_at",
        "max_concurrency",
        "max_attempts",
        "timeout_seconds",
        "queued",
        "in_flight",
        "running",
        "last_run",
        "recent",
    }
    assert nightly["triggers"] == [
        {
            "kind": "cron",
            "spec": "0 0 6 * * *",
            "time_zone": "UTC",
            "summary": "Every day at 06:00 UTC",
            "next_at": "2026-10-03T06:00:00+00:00",
        }
    ]
    assert nightly["next_at"] == "2026-10-03T06:00:00+00:00"
    assert (nightly["queued"], nightly["in_flight"], nightly["running"]) == (2, 1, 0)
    assert nightly["timeout_seconds"] == 600.0 and nightly["max_attempts"] == 3
    assert [r["run_id"] for r in nightly["recent"]] == ["nightly:3", "nightly:2"]
    assert set(nightly["last_run"]) == RUN_KEYS
    assert nightly["last_run"]["duration_ms"] == 30500
    assert nightly["last_run"]["trigger"] == {
        "kind": "schedule",
        "scheduler": "abi.jobs.zen.schedule.m.j.0",
    }
    assert jobs["acme.jobs/sync"]["running"] == 1
    assert jobs["acme.jobs/sync"]["queued"] is None
    assert jobs["acme.other/report"]["location"] == "remote"
    assert jobs["acme.other/report"]["instances"] == 2


def test_runs_with_filters_and_cursor(client):
    page = client.get(f"{BASE}/runs", params={"limit": 2}).json()
    rest = client.get(f"{BASE}/runs", params={"limit": 2, "before": page["next"]}).json()
    failed = client.get(f"{BASE}/runs", params={"status": "failed,TIMED_OUT"}).json()
    scheduled = client.get(
        f"{BASE}/runs", params={"trigger": "schedule", "module": "acme.jobs"}
    ).json()

    assert [r["key"] for r in page["runs"]] == ["acme.jobs/sync:9", "acme.other/report:1"]
    assert page["next"] == "2026-10-02T07:00:01+00:00"
    assert [r["run_id"] for r in rest["runs"]] == ["nightly:3", "nightly:2"]
    assert [r["run_id"] for r in failed["runs"]] == ["report:1", "nightly:2"]
    assert failed["next"] is None
    assert [r["run_id"] for r in scheduled["runs"]] == ["nightly:3", "nightly:2"]
    assert set(page["runs"][0]) == RUN_KEYS
    assert page["runs"][0]["duration_ms"] is None  # still running


def test_run_detail(client):
    body = client.get(f"{BASE}/runs/acme.jobs/nightly:3").json()

    assert set(body) == RUN_KEYS | {"payload", "result", "logs", "trace_url"}
    assert body["result"] == {"rows": 3} and body["logs"] == ["synced 3 rows"]
    assert body["trace_url"] == "http://jaeger:16686/trace/" + "b" * 32
    assert client.get(f"{BASE}/runs/acme.jobs/sync:9").json()["trace_url"] is None
    missing = client.get(f"{BASE}/runs/acme.jobs/nightly:99")
    assert missing.status_code == 404
    assert missing.json()["detail"]["source"] == "jobs"


def test_trigger_is_audited(client, control, audit):
    response = client.post(f"{BASE}/acme.jobs/nightly/trigger", json={"payload": {"full": True}})

    assert response.status_code == 202
    assert response.json() == {"run_id": "nightly:101", "key": "acme.jobs/nightly:101"}
    assert control.triggered == [("acme.jobs", "nightly", {"full": True})]
    assert [(r.action.operation, r.action.resource_id, r.phase) for r in audit.records] == [
        ("trigger", "acme.jobs/nightly", "requested"),
        ("trigger", "acme.jobs/nightly", "succeeded"),
    ]
    assert client.post(f"{BASE}/acme.jobs/nightly/trigger").status_code == 202  # empty body
    assert client.post(f"{BASE}/acme.jobs/nope/trigger", json={}).status_code == 404


def test_cancel(client, control):
    response = client.post(f"{BASE}/runs/acme.jobs/sync:9/cancel")
    refused = client.post(f"{BASE}/runs/acme.jobs/nightly:3/cancel")

    assert response.status_code == 202 and response.json() == {"ok": True}
    assert control.cancelled == [("acme.jobs", "sync", "sync:9")]
    assert refused.status_code == 409 and refused.json()["detail"]["source"] == "jobs"
    assert client.post(f"{BASE}/runs/acme.jobs/x:1/cancel").status_code == 404


def test_unavailable_sources_and_audit(control):
    off = SourceUnavailable("runs", "NATS mode is off")
    client = _client(
        _admin(
            control,
            InMemoryAuditLog(fail="db down"),
            runs=off,
            queue=SourceUnavailable("queue", "x"),
        )
    )

    overview = client.get(BASE).json()
    assert overview["sources"]["runs"] == {"available": False, "reason": "NATS mode is off"}
    runs = client.get(f"{BASE}/runs")
    assert runs.status_code == 503 and runs.json()["detail"] == {
        "source": "runs",
        "reason": "NATS mode is off",
    }
    trigger = client.post(f"{BASE}/acme.jobs/nightly/trigger", json={})
    assert trigger.status_code == 503 and trigger.json()["detail"]["source"] == "audit"
    assert control.triggered == []


def test_failures_since_a_time(client):
    body = client.get(f"{BASE}/failures", params={"since": "2026-09-01T00:00:00+00:00"}).json()

    assert body["since"] == "2026-09-01T00:00:00+00:00"
    assert body["count"] == 2 and body["more"] is False
    assert [r["run_id"] for r in body["runs"]] == ["report:1", "nightly:2"]
    assert set(body["runs"][0]) == RUN_KEYS
    assert client.get(f"{BASE}/failures").json()["count"] == 1  # the last day
