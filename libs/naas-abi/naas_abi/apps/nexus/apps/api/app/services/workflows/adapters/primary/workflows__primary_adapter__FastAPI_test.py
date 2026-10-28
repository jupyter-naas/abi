from dataclasses import replace
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_jobs import (
    InMemoryJobCatalog,
    InMemoryJobControl,
    InMemoryJobQueue,
    InMemoryJobRunStore,
    InMemoryStepStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.json_schema_validator import (
    JsonSchemaValidator,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.port import SourceUnavailable
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.primary.workflows__primary_adapter__FastAPI import (
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import get_workflows_service
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService

BASE = "/api/workflows"
NOW = datetime(2026, 10, 2, 13, 0, 0, tzinfo=UTC)

RUN_KEYS = {
    "key",
    "module_id",
    "workflow",
    "run_id",
    "status",
    "attempt",
    "max_attempts",
    "fired_at",
    "started_at",
    "finished_at",
    "duration_ms",
    "error",
    "trace_id",
    "result",
    "steps",
    "steps_truncated",
}


@pytest.fixture
def control():
    return InMemoryJobControl()


@pytest.fixture
def audit():
    return InMemoryAuditLog()


class NoWait:
    """``?wait`` without waiting: time jumps."""

    now = 0.0

    def monotonic(self):
        return self.now

    async def sleep(self, seconds):
        self.now += seconds


def _service(control, audit, **overrides):
    parts = {
        "catalogs": [
            InMemoryJobCatalog(fixtures.job_definitions() + fixtures.workflow_definitions())
        ],
        "runs": InMemoryJobRunStore(fixtures.job_runs() + fixtures.workflow_runs()),
        "control": control,
        "queue": InMemoryJobQueue(),
        "audit": audit,
        "project": "zen",
        "clock": lambda: NOW,
        "steps": InMemoryStepStore(fixtures.workflow_steps()),
        "validator": JsonSchemaValidator(),
    }
    parts.update(overrides)
    clock = NoWait()
    return WorkflowsService(
        JobsAdminService(**parts),
        sleep=clock.sleep,
        monotonic=clock.monotonic,
        clock=lambda: NOW,
    )


def _client(service, user="admin", *, credential="session"):
    """``user``: ``"admin"`` (``root``, a platform admin), ``"member"`` (``u1``,
    who holds nothing) or None (no credential). ``credential``: how they signed
    in, a ``session`` or their personal API key (``api-key``)."""
    app = FastAPI()
    app.include_router(router, prefix=BASE)
    app.dependency_overrides[get_workflows_service] = lambda: service
    if user:
        uid = "root" if user == "admin" else "u1"
        app.dependency_overrides[get_current_user] = lambda: User.model_construct(
            id=uid, email=f"{uid}@example.com", name=uid
        )

        @app.middleware("http")
        async def signed_in(request, call_next):
            request.state.nexus_credential = SimpleNamespace(kind=credential, user_id=uid)
            return await call_next(request)

    else:
        app.dependency_overrides[get_current_user] = lambda: None
    return TestClient(app)


@pytest.fixture
def client(control, audit):
    return _client(_service(control, audit))


ROUTES = [
    ("GET", ""),
    ("POST", "/acme.flows/ingest/runs"),
    ("GET", "/acme.flows/runs/ingest:5"),
    ("POST", "/acme.flows/runs/ingest:6/cancel"),
]


@pytest.mark.parametrize("method,path", ROUTES)
def test_a_user_who_is_not_a_platform_admin_gets_403_and_nothing_happens(
    control, audit, method, path
):
    client = _client(_service(control, audit), user="member")

    response = client.request(
        method, BASE + path, json={"filter": "news"} if method == "POST" else None
    )

    assert response.status_code == 403
    assert control.triggered == [] and control.cancelled == [] and audit.records == []


@pytest.mark.parametrize("method,path", ROUTES)
def test_no_credentials_get_401_and_a_wrong_key_too(control, audit, method, path):
    client = _client(_service(control, audit), user=None)

    assert client.request(method, BASE + path).status_code == 401
    wrong = client.request(method, BASE + path, headers={"Authorization": "Bearer nope"})
    assert wrong.status_code == 401
    assert control.triggered == [] and control.cancelled == [] and audit.records == []


def test_a_platform_admins_personal_key_reaches_every_route(control, audit):
    client = _client(_service(control, audit), credential="api-key")

    assert client.get(BASE).status_code == 200
    assert client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news"}).status_code == 202
    assert client.get(f"{BASE}/acme.flows/runs/ingest:5").status_code == 200
    assert client.post(f"{BASE}/acme.flows/runs/ingest:6/cancel").status_code == 202


def test_a_start_and_a_cancel_with_a_personal_key_are_audited_for_its_user(control, audit):
    client = _client(_service(control, audit), credential="api-key")

    client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news"})
    client.post(f"{BASE}/acme.flows/runs/ingest:6/cancel")

    assert [
        (
            r.action.actor_id,
            r.action.via,
            r.action.service,
            r.action.operation,
            r.action.resource_id,
            r.phase,
        )
        for r in audit.records
    ] == [
        ("root", "api_key", "jobs", "trigger", "acme.flows/ingest", "requested"),
        ("root", "api_key", "jobs", "trigger", "acme.flows/ingest", "succeeded"),
        ("root", "api_key", "jobs", "cancel", "acme.flows/ingest:6", "requested"),
        ("root", "api_key", "jobs", "cancel", "acme.flows/ingest:6", "succeeded"),
    ]


def test_list_has_workflows_only_with_schemas_and_trigger_inputs(client):
    body = client.get(BASE).json()
    flows = {w["key"]: w for w in body["workflows"]}

    assert sorted(flows) == ["acme.flows/ingest", "acme.flows/map_item"]
    ingest = flows["acme.flows/ingest"]
    assert ingest["kind"] == "workflow" and ingest["location"] == "remote"
    assert ingest["input_schema"] == fixtures.INGEST_INPUT_SCHEMA
    assert ingest["output_schema"] == fixtures.INGEST_OUTPUT_SCHEMA
    assert ingest["triggers"] == [
        {"kind": "cron", "spec": "0 0 6 * * *", "time_zone": "UTC", "input": {"filter": "news"}}
    ]
    assert flows["acme.flows/map_item"]["input_schema"] is None
    assert body["sources"]["engine"] == {"available": True, "reason": ""}


def test_a_start_is_accepted_with_its_run_id_and_audited_for_the_user(client, control, audit):
    response = client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news", "limit": 5})

    assert response.status_code == 202
    body = response.json()
    assert set(body) == RUN_KEYS
    assert (body["key"], body["run_id"], body["status"], body["workflow"]) == (
        "acme.flows/ingest:101",
        "ingest:101",
        "QUEUED",
        "ingest",
    )
    assert control.triggered == [("acme.flows", "ingest", {"filter": "news", "limit": 5})]
    assert [(r.action.actor_id, r.action.via, r.phase) for r in audit.records] == [
        ("root", "user", "requested"),
        ("root", "user", "succeeded"),
    ]


def test_an_empty_body_is_an_empty_input(client, control):
    # map_item declares no schema, so nothing is required of it.
    assert client.post(f"{BASE}/acme.flows/map_item/runs").status_code == 202
    assert control.triggered == [("acme.flows", "map_item", {})]


def test_invalid_input_is_a_422_with_the_faults_and_starts_nothing(client, control, audit):
    response = client.post(f"{BASE}/acme.flows/ingest/runs", json={"limit": 0, "dry_run": "yes"})

    assert response.status_code == 422
    detail = response.json()["detail"]
    assert detail["source"] == "workflows"
    assert detail["reason"] == "The input does not match the workflow's input schema"
    assert detail["errors"] == [
        {"path": "", "message": "'filter' is a required property"},
        {"path": "/dry_run", "message": "'yes' is not of type 'boolean'"},
        {"path": "/limit", "message": "0 is less than the minimum of 1"},
    ]
    assert control.triggered == [] and audit.records == []


def test_a_body_that_is_not_an_object_is_a_422_too(client, control):
    assert client.post(f"{BASE}/acme.flows/ingest/runs", json=["filter"]).status_code == 422
    assert (
        client.post(
            f"{BASE}/acme.flows/ingest/runs",
            content="{nope",
            headers={"content-type": "application/json"},
        ).status_code
        == 422
    )
    assert control.triggered == []


def test_the_idempotency_key_makes_a_repeated_start_the_same_run(client, control, audit):
    headers = {"Idempotency-Key": "import-1"}

    first = client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news"}, headers=headers)
    again = client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news"}, headers=headers)

    assert first.json()["run_id"] == again.json()["run_id"] == "ingest:101"
    assert control.keys == ["import-1", "import-1"]
    assert len(audit.records) == 4  # each start, repeated or not, is on record


def test_repeating_a_start_whose_run_is_over_answers_200_with_its_result(control, audit):
    done = replace(
        fixtures.workflow_runs()[1],
        run_id="ingest:101",
        result={"count": 9},
        fired_at=NOW.isoformat(),
    )
    client = _client(
        _service(control, audit, runs=InMemoryJobRunStore(fixtures.workflow_runs() + [done]))
    )

    response = client.post(
        f"{BASE}/acme.flows/ingest/runs",
        json={"filter": "news"},
        headers={"Idempotency-Key": "import-1"},
    )

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["result"]) == ("SUCCEEDED", {"count": 9})


def test_an_idempotency_key_that_cannot_be_a_header_value_is_a_422(client, control):
    response = client.post(
        f"{BASE}/acme.flows/ingest/runs",
        json={"filter": "news"},
        headers={"Idempotency-Key": "k" * 201},
    )

    assert response.status_code == 422
    assert control.triggered == []


def test_starting_something_that_is_not_a_workflow_is_a_404(client, control):
    assert client.post(f"{BASE}/acme.jobs/nightly/runs", json={}).status_code == 404
    assert client.post(f"{BASE}/acme.flows/nope/runs", json={}).status_code == 404
    assert control.triggered == []


def test_wait_returns_the_result_with_200_when_the_run_ends_in_time(control, audit):
    done = replace(
        fixtures.workflow_runs()[1],
        run_id="ingest:101",
        result={"count": 7},
        fired_at=NOW.isoformat(),
    )
    service = _service(control, audit, runs=InMemoryJobRunStore(fixtures.workflow_runs() + [done]))

    response = _client(service).post(
        f"{BASE}/acme.flows/ingest/runs", params={"wait": 5}, json={"filter": "news"}
    )

    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["result"]) == ("SUCCEEDED", {"count": 7})
    assert body["finished_at"] and body["duration_ms"] == 9000


def test_wait_returns_a_failed_run_with_its_error(control, audit):
    failed = replace(
        fixtures.workflow_runs()[2], job="ingest", run_id="ingest:101", fired_at=NOW.isoformat()
    )
    service = _service(
        control, audit, runs=InMemoryJobRunStore(fixtures.workflow_runs() + [failed])
    )

    response = _client(service).post(
        f"{BASE}/acme.flows/ingest/runs", params={"wait": 5}, json={"filter": "news"}
    )

    assert response.status_code == 200
    assert (response.json()["status"], response.json()["error"]) == (
        "FAILED",
        "ValueError: bad item",
    )


def test_wait_that_runs_out_answers_202_with_the_run_still_going(client, control):
    response = client.post(
        f"{BASE}/acme.flows/ingest/runs", params={"wait": 3}, json={"filter": "news"}
    )

    assert response.status_code == 202
    assert response.json()["status"] == "QUEUED" and response.json()["run_id"] == "ingest:101"
    assert len(control.triggered) == 1


@pytest.mark.parametrize("wait", ["-1", "121", "soon"])
def test_a_wait_out_of_range_is_a_422_and_starts_nothing(client, control, wait):
    response = client.post(
        f"{BASE}/acme.flows/ingest/runs", params={"wait": wait}, json={"filter": "news"}
    )

    assert response.status_code == 422
    assert control.triggered == []


def test_status_has_result_error_and_steps_with_child_links(client):
    body = client.get(f"{BASE}/acme.flows/runs/ingest:5").json()

    assert set(body) == RUN_KEYS
    assert (body["status"], body["result"], body["steps_truncated"]) == (
        "SUCCEEDED",
        {"count": 2},
        False,
    )
    assert [(s["key"], s["kind"], s["status"], s["attempt"]) for s in body["steps"]] == [
        ("fetch", "step", "SUCCEEDED", 2),
        ("map[0]", "call", "SUCCEEDED", 1),
        ("map[1]", "call", "FAILED", 1),
    ]
    assert body["steps"][1]["child"] == {
        "module_id": "acme.flows",
        "workflow": "map_item",
        "run_id": "map_item:1",
        "key": "acme.flows/map_item:1",
    }
    assert body["steps"][2]["error"].startswith("ChildRunFailed")
    assert body["steps"][0]["child"] is None
    # A child's run is a workflow run like any other.
    assert (
        client.get(f"{BASE}/acme.flows/runs/map_item:2").json()["error"] == "ValueError: bad item"
    )


@pytest.mark.parametrize(
    "path",
    [
        "/acme.jobs/runs/nightly:3",
        "/acme.flows/runs/nope:1",
        "/acme.flows/runs/garbage",
        "/acme.flows/runs/ingest:77",  # pruned, or never recorded
        "/no.module/runs/ingest:1",
    ],
)
def test_status_of_something_that_is_not_a_workflow_run_is_a_404(client, path):
    response = client.get(BASE + path)

    assert response.status_code == 404
    assert response.json()["detail"]["source"] == "workflows"


def test_cancel_is_accepted_and_audited(client, control, audit):
    response = client.post(f"{BASE}/acme.flows/runs/ingest:6/cancel")

    assert response.status_code == 202 and response.json() == {"ok": True}
    assert control.cancelled == [("acme.flows", "ingest", "ingest:6")]
    assert [(r.action.operation, r.action.resource_id, r.phase) for r in audit.records] == [
        ("cancel", "acme.flows/ingest:6", "requested"),
        ("cancel", "acme.flows/ingest:6", "succeeded"),
    ]


def test_cancel_of_a_finished_run_is_a_409_and_of_a_plain_jobs_run_a_404(client, control, audit):
    assert client.post(f"{BASE}/acme.flows/runs/ingest:5/cancel").status_code == 409
    assert client.post(f"{BASE}/acme.jobs/runs/sync:9/cancel").status_code == 404
    assert client.post(f"{BASE}/acme.flows/runs/ingest:99/cancel").status_code == 404
    assert control.cancelled == [] and audit.records == []


def test_without_an_audit_record_nothing_is_started_or_cancelled(control):
    client = _client(_service(control, InMemoryAuditLog(fail="db down")))

    start = client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news"})
    cancel = client.post(f"{BASE}/acme.flows/runs/ingest:6/cancel")

    assert (start.status_code, cancel.status_code) == (503, 503)
    assert start.json()["detail"]["source"] == "audit"
    assert control.triggered == [] and control.cancelled == []


def test_the_broker_being_down_is_a_503(audit):
    client = _client(_service(InMemoryJobControl(fail="no broker"), audit))

    response = client.post(f"{BASE}/acme.flows/ingest/runs", json={"filter": "news"})

    assert response.status_code == 503
    assert response.json()["detail"] == {"source": "jobs", "reason": "no broker"}


def test_unavailable_run_records_are_a_503_on_status(control, audit):
    client = _client(_service(control, audit, runs=SourceUnavailable("runs", "NATS mode is off")))

    response = client.get(f"{BASE}/acme.flows/runs/ingest:5")

    assert response.status_code == 503 and response.json()["detail"]["source"] == "runs"
