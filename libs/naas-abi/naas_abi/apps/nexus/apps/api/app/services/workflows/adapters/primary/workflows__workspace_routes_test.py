"""Workflows and pipelines in a workspace: by module scope, the caller's own runs."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.authz import ModuleScope
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_jobs import (
    InMemoryJobCatalog,
    InMemoryJobControl,
    InMemoryJobQueue,
    InMemoryJobRunStore,
    InMemoryStepStore,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.in_memory_resources import (  # noqa: E501
    InMemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import (
    JobDefinition,
    JobRun,
    RunTrigger,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs_service import JobsAdminService
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.primary.workflows__primary_adapter__FastAPI import (  # noqa: E501
    workspace_router,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.secondary.in_memory import (
    InMemoryRunOwners,
)
from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import get_workflows_service
from naas_abi.apps.nexus.apps.api.app.services.workflows.service import WorkflowsService

NOW = datetime(2026, 10, 2, 13, 0, 0, tzinfo=UTC)
WS = "/api/workspaces/ws-1/workflows"
PIPELINE = JobDefinition("acme.flows", "pipeline.daily", "", "remote", kind="workflow")
INGEST = ModuleScope("workflow", "acme.flows", "ingest")
DAILY = ModuleScope("pipeline", "acme.flows", "pipeline.daily")


class World:
    def __init__(self, nexus_iam) -> None:
        self.iam = nexus_iam
        self.scope = nexus_iam.workspace("org-1", "ws-1")
        nexus_iam.workspace("org-1", "ws-2")
        for user in ("owner", "admin", "member", "viewer"):
            nexus_iam.grant(user, user, self.scope)
        nexus_iam.grant("other", "member", self.scope)
        self.control = InMemoryJobControl()
        self.runs = InMemoryJobRunStore(fixtures.job_runs() + fixtures.workflow_runs())
        self.owners = InMemoryRunOwners()
        self.service = WorkflowsService(
            JobsAdminService(
                catalogs=[
                    InMemoryJobCatalog(
                        fixtures.job_definitions() + fixtures.workflow_definitions() + [PIPELINE]
                    )
                ],
                runs=self.runs,
                control=self.control,
                queue=InMemoryJobQueue(),
                audit=InMemoryAuditLog(),
                project="zen",
                clock=lambda: NOW,
                steps=InMemoryStepStore(fixtures.workflow_steps()),
            ),
            clock=lambda: NOW,
            owners=self.owners,
        )

    def client(self, user_id: str) -> TestClient:
        app = FastAPI()
        app.include_router(workspace_router, prefix="/api/workspaces/{workspace_id}/workflows")
        app.dependency_overrides[get_workflows_service] = lambda: self.service
        app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
            id=user_id, email=f"{user_id}@example.com", name=user_id
        )
        return TestClient(app)

    def host_records(self, run_id: str, job: str = "ingest") -> None:
        """The host takes the run: its record exists, fired after the start."""
        self.runs.runs.append(
            JobRun(
                "acme.flows",
                job,
                run_id,
                "SUCCEEDED",
                trigger=RunTrigger("manual"),
                fired_at=NOW.isoformat(),
                started_at=NOW.isoformat(),
                finished_at=NOW.isoformat(),
                result={"ok": True},
            )
        )


@pytest.fixture
def world(nexus_iam) -> World:
    return World(nexus_iam)


def _listed(client: TestClient, path: str = WS) -> set[str]:
    response = client.get(path)
    assert response.status_code == 200, response.text
    return {w["name"] for w in response.json()["workflows"]}


@pytest.mark.parametrize("role", ["viewer", "member"])
def test_viewers_and_members_see_and_start_nothing_by_default(world, role) -> None:
    client = world.client(role)
    assert _listed(client) == set()
    assert client.post(f"{WS}/acme.flows/ingest/runs", json={}).status_code == 403
    assert world.control.triggered == []


@pytest.mark.parametrize("role", ["admin", "owner"])
def test_admins_see_every_workflow_and_pipeline(world, role) -> None:
    body = world.client(role).get(WS).json()
    assert {(w["name"], w["type"]) for w in body["workflows"]} == {
        ("ingest", "workflow"),
        ("map_item", "workflow"),
        ("pipeline.daily", "pipeline"),
    }


def test_a_stranger_is_refused_the_workspace(world) -> None:
    world.iam.user("stranger")
    assert world.client("stranger").get(WS).status_code == 403


def test_a_grant_of_one_workflow_lists_and_starts_it_alone(world) -> None:
    world.iam.allow_scope("member", INGEST, world.scope)
    client = world.client("member")
    assert _listed(client) == {"ingest"}
    assert client.post(f"{WS}/acme.flows/ingest/runs", json={"filter": "news"}).status_code == 202
    assert client.post(f"{WS}/acme.flows/map_item/runs", json={}).status_code == 403
    assert client.post(f"{WS}/acme.flows/pipeline.daily/runs", json={}).status_code == 403
    assert world.control.triggered == [("acme.flows", "ingest", {"filter": "news"})]
    # Not in another workspace.
    assert (
        world.client("member")
        .post("/api/workspaces/ws-2/workflows/acme.flows/ingest/runs", json={})
        .status_code
        == 403
    )


def test_a_grant_of_one_pipeline_lists_and_starts_it_alone(world) -> None:
    world.iam.allow_scope("member", DAILY, world.scope)
    client = world.client("member")
    assert _listed(client) == {"pipeline.daily"}
    assert client.post(f"{WS}/acme.flows/pipeline.daily/runs", json={}).status_code == 202
    assert client.post(f"{WS}/acme.flows/ingest/runs", json={}).status_code == 403


def test_a_user_reads_their_own_runs_with_the_runs_scope(world) -> None:
    for user in ("member", "other"):
        world.iam.allow_scope(user, INGEST, world.scope)
    started = world.client("member").post(f"{WS}/acme.flows/ingest/runs", json={"filter": "x"})
    run_id = started.json()["run_id"]
    world.host_records(run_id)
    path = f"{WS}/acme.flows/runs/{run_id}"

    member = world.client("member")
    # Starting is not reading: the runs need their own grant.
    assert member.get(path).status_code == 403
    assert member.get(f"{WS}/runs").json() == {"runs": []}
    world.iam.allow(
        "member",
        ["module:ReadWorkflowRuns"],
        ["${scope}:module:workflow/acme.flows/ingest"],
        world.scope,
    )
    assert member.get(path).json()["result"] == {"ok": True}
    assert [r["run_id"] for r in member.get(f"{WS}/runs").json()["runs"]] == [run_id]

    # Another user's run, an old run of the host, another workspace: not found.
    world.iam.allow(
        "other",
        ["module:ReadWorkflowRuns"],
        ["${scope}:module:workflow/acme.flows/ingest"],
        world.scope,
    )
    assert world.client("other").get(path).status_code == 404
    assert member.get(f"{WS}/acme.flows/runs/ingest:5").status_code == 404
    assert member.get(f"/api/workspaces/ws-2/workflows/acme.flows/runs/{run_id}").status_code in (
        403,
        404,
    )


def test_an_idempotency_key_is_the_callers_own(world) -> None:
    for user in ("member", "other"):
        world.iam.allow_scope(user, INGEST, world.scope)
    key = {"Idempotency-Key": "import-1"}
    first = world.client("member").post(f"{WS}/acme.flows/ingest/runs", json={}, headers=key)
    again = world.client("member").post(f"{WS}/acme.flows/ingest/runs", json={}, headers=key)
    theirs = world.client("other").post(f"{WS}/acme.flows/ingest/runs", json={}, headers=key)
    assert first.json()["run_id"] == again.json()["run_id"] != theirs.json()["run_id"]
    assert world.owners.rows[("acme.flows", first.json()["run_id"])].user_id == "member"
