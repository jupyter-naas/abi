"""``/api/iam/admin/capabilities``: the capability groups of a level (an organization's
"Workflow runners", the platform's "Models · all"), listed for whoever may list the
groups there and made on demand by whoever may create groups (and policies) there.
Made as ``api`` (``iam/capabilities.ensure_capability``) once the caller is checked;
audited first. And the group markers (``membership_of``, ``level_group``) on a group's
view."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.capabilities import (
    MODELS_ALL,
    WORKFLOW_RUNNERS,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.container_defaults import make_org
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, workspace_container
from naas_abi.apps.nexus.apps.api.app.services.iam_admin import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.primary.iam_admin__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import MemoryAudit
from naas_abi_core.engine.call_context import as_service_account

ORG = org_container("org-1")


def _by_header(request: Request) -> SimpleNamespace:
    user = request.headers.get("x-user")
    if not user:
        raise HTTPException(401, "Not authenticated")
    return SimpleNamespace(id=user, email=f"{user}@example.com", name=user)


@pytest.fixture
def world(team):
    """``root`` (platform admin); ``admin`` an org admin of ``org-1``, ``member`` a member;
    "<org-1> access" made as Nexus makes it."""
    team.platform_admin("root")
    with as_service_account("api"):
        org = make_org(team.iam, "org-1", "Org One")
    access = {"org-1": org.access_policy_id}

    async def org_access_of(org_id: str) -> str | None:
        return access.get(org_id)

    audit = MemoryAudit()
    previous = runtime.configure(
        lambda: IamAdminService(EngineIamGateway(), audit, org_access_of=org_access_of)
    )
    app = FastAPI()
    app.include_router(router, prefix="/api/iam/admin")
    app.dependency_overrides[get_current_user_required] = _by_header
    yield SimpleNamespace(nexus=team, client=TestClient(app), audit=audit, org_access=org)
    runtime.configure(previous)


def _get(world, path: str, user: str = "root"):
    return world.client.get(f"/api/iam/admin{path}", headers={"x-user": user})


def _post(world, path: str, user: str = "root", **body):
    return world.client.post(f"/api/iam/admin{path}", json=body, headers={"x-user": user})


def test_an_org_lists_workflow_runners_not_made_yet(world):
    answer = _get(world, f"/capabilities?scope={ORG}", "admin")
    assert answer.status_code == 200, answer.text
    (row,) = answer.json()["capabilities"]
    assert row == {
        "capability": "workflow_runners",
        "name": WORKFLOW_RUNNERS,
        "owner_scope": ORG,
        "group_id": None,
        "policy_id": None,
        "can_create": True,
    }


def test_an_org_admin_makes_workflow_runners_once_bounded_by_the_org(world):
    made = _post(world, "/capabilities", "admin", capability="workflow_runners", scope=ORG)
    assert made.status_code == 200, made.text
    body = made.json()
    assert body["name"] == WORKFLOW_RUNNERS and body["group_id"] and body["policy_id"]
    assert body["can_create"] is False
    with as_service_account("api"):
        policy = world.nexus.iam.get_policy(body["policy_id"])
        group = world.nexus.iam.get_group(body["group_id"])
    assert (group.owner_scope, policy.parent_id) == (ORG, world.org_access.access_policy_id)
    # Idempotent: the same group again, and listed.
    again = _post(world, "/capabilities", "admin", capability="workflow_runners", scope=ORG)
    assert again.json()["group_id"] == body["group_id"]
    (row,) = _get(world, f"/capabilities?scope={ORG}", "admin").json()["capabilities"]
    assert row["group_id"] == body["group_id"]
    assert world.audit.phases("ensure_capability")[:2] == ["requested", "succeeded"]


def test_a_workspace_page_reads_its_organization_s_runners(world):
    scope = workspace_container("org-1", "ws-1")
    (row,) = _get(world, f"/capabilities?scope={scope}", "admin").json()["capabilities"]
    assert (row["capability"], row["owner_scope"]) == ("workflow_runners", ORG)


def test_a_member_or_a_stranger_makes_no_capability_group(world):
    for user in ("member", "stranger"):
        refused = _post(world, "/capabilities", user, capability="workflow_runners", scope=ORG)
        assert refused.status_code == 403, (user, refused.text)
    assert _get(world, f"/capabilities?scope={ORG}", "stranger").status_code == 403


def test_models_all_is_the_platform_s_made_by_a_platform_admin_only(world):
    (row,) = _get(world, "/capabilities").json()["capabilities"]
    assert (row["capability"], row["name"], row["owner_scope"]) == (
        "models_all",
        MODELS_ALL,
        "abi:",
    )
    assert _post(world, "/capabilities", "admin", capability="models_all").status_code == 403
    made = _post(world, "/capabilities", capability="models_all")
    assert made.status_code == 200, made.text
    with as_service_account("api"):
        group = world.nexus.iam.get_group(made.json()["group_id"])
    assert (group.name, group.owner_scope) == (MODELS_ALL, "abi:")


def test_a_capability_of_another_level_is_refused(world):
    wrong = _post(world, "/capabilities", capability="models_all", scope=ORG)
    assert wrong.status_code == 422
    unknown = _post(world, "/capabilities", capability="everything", scope=ORG)
    assert unknown.status_code == 422


def test_an_org_without_its_access_policy_gets_no_runners(world):
    world.nexus.org("org-2")
    refused = _post(
        world,
        "/capabilities",
        capability="workflow_runners",
        scope=org_container("org-2"),
    )
    assert refused.status_code == 422
    assert "access policy" in refused.json()["detail"]


def test_a_group_view_carries_its_markers(world):
    w = workspace_container("org-1", "ws-1")
    with as_service_account("api"):
        members = world.nexus.iam.create_group("ws-1 workspace", scope=w, membership_of=w)
        level = world.nexus.iam.create_group("Members")
        world.nexus.iam.mark_group(level.id, membership_of=None, level=True)
    found = {g["id"]: g for g in _get(world, f"/groups?scope={w}").json()["items"]}
    assert (found[members.id]["membership_of"], found[members.id]["level_group"]) == (w, False)
    platform = {g["id"]: g for g in _get(world, "/groups").json()["items"]}
    assert (platform[level.id]["membership_of"], platform[level.id]["level_group"]) == (None, True)
