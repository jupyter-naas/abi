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


# -- the workspace's set, and on or off there ------------------------------------------


@pytest.fixture
def switches(world):
    """Workflows on and off in the workspace, as its settings record them."""
    from naas_abi.apps.nexus.apps.api.app.services.visibility.testing import (
        visibility_installed,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workflows.adapters.secondary.in_memory import (
        InMemoryWorkflowVisibility,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workflows.factory import (
        get_workflow_visibility,
    )
    from naas_abi.apps.nexus.apps.api.app.services.workflows.visibility import (
        WorkflowsVisibility,
    )

    store = InMemoryWorkflowVisibility()
    reader = WorkflowsVisibility(store)
    client = world.client

    def with_store(user_id: str) -> TestClient:
        made = client(user_id)
        made.app.dependency_overrides[get_workflow_visibility] = lambda: store
        return made

    world.client = with_store
    with visibility_installed({"workflow": reader, "pipeline": reader}):
        yield world


def test_a_workspace_lists_only_the_workflows_of_its_set(world) -> None:
    world.iam.platform_admin("root")
    world.iam.put_set("org-1", "ws-1", modules=["pipeline/acme.flows/*"])
    for who in ("admin", "root"):
        assert _listed(world.client(who)) == {"pipeline.daily"}, who
    world.iam.put_set("org-1", "ws-1", modules=["acme.other"])
    assert _listed(world.client("root")) == set()


@pytest.mark.parametrize("role", ["viewer", "member"])
def test_viewers_and_members_neither_list_nor_switch_workflow_settings(switches, role) -> None:
    client = switches.client(role)
    assert client.get(f"{WS}/settings").status_code == 403
    off = {"type": "workflow", "module_id": "acme.flows", "name": "ingest", "enabled": False}
    assert client.put(f"{WS}/settings", json=off).status_code == 403


def test_admins_switch_a_workflow_off_for_everyone_and_back_on(switches) -> None:
    switches.iam.allow_scope("member", INGEST, switches.scope)
    switches.iam.platform_admin("root")
    admin = switches.client("admin")
    listed = admin.get(f"{WS}/settings").json()["workflows"]
    assert {(w["type"], w["name"], w["enabled"]) for w in listed} == {
        ("workflow", "ingest", True),
        ("workflow", "map_item", True),
        ("pipeline", "pipeline.daily", True),
    }
    off = {"type": "workflow", "module_id": "acme.flows", "name": "ingest", "enabled": False}
    assert admin.put(f"{WS}/settings", json=off).status_code == 200
    # Refused to everyone who could start it, and left out of their lists.
    for who in ("member", "admin", "root"):
        client = switches.client(who)
        refused = client.post(f"{WS}/acme.flows/ingest/runs", json={})
        assert refused.status_code == 403, who
        assert refused.json()["detail"] == "This workflow is turned off in this workspace"
        assert "ingest" not in _listed(client), who
    assert switches.control.triggered == []
    # Its admins still list it, off, in the settings.
    listed = admin.get(f"{WS}/settings").json()["workflows"]
    assert ("ingest", False) in {(w["name"], w["enabled"]) for w in listed}
    assert admin.put(f"{WS}/settings", json={**off, "enabled": True}).status_code == 200
    assert (
        switches.client("member").post(f"{WS}/acme.flows/ingest/runs", json={}).status_code == 202
    )


def test_a_pipeline_switched_off_is_refused(switches) -> None:
    switches.iam.allow_scope("member", DAILY, switches.scope)
    off = {
        "type": "pipeline",
        "module_id": "acme.flows",
        "name": "pipeline.daily",
        "enabled": False,
    }
    assert switches.client("admin").put(f"{WS}/settings", json=off).status_code == 200
    member = switches.client("member")
    assert _listed(member) == set()
    refused = member.post(f"{WS}/acme.flows/pipeline.daily/runs", json={})
    assert refused.status_code == 403
    assert refused.json()["detail"] == "This pipeline is turned off in this workspace"


def test_workflow_settings_list_the_set_and_turn_on_nothing_outside_it(switches) -> None:
    switches.iam.put_set("org-1", "ws-1", modules=["workflow/acme.flows/ingest"])
    admin = switches.client("admin")
    assert [w["name"] for w in admin.get(f"{WS}/settings").json()["workflows"]] == ["ingest"]
    on = {"type": "pipeline", "module_id": "acme.flows", "name": "pipeline.daily", "enabled": True}
    refused = admin.put(f"{WS}/settings", json=on)
    assert refused.status_code == 403
    assert "not in the workspace's set" in refused.json()["detail"]
    # Off is always allowed.
    assert admin.put(f"{WS}/settings", json={**on, "enabled": False}).status_code == 200
