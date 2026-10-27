"""The sets routes (the modules × workspaces page) over a real IAM: who reads and
who changes which set, the refusal of a workspace wider than its org, the audit."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin import runtime
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.primary.iam_admin__primary_adapter__FastAPI import (  # noqa: E501
    router,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.adapters.secondary.engine import (
    EngineIamGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.port import (
    OrganizationScopes,
    ScopeName,
)
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.service import IamAdminService
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.testing import (
    MemoryAudit,
    MemoryDirectory,
)
from naas_abi.apps.nexus.apps.api.app.services.modules import scopes
from naas_abi_core.engine.call_context import as_service_account

MODULES = [
    {
        "module": "people",
        "agents": [{"name": "A"}, {"name": "B"}],
        "apps": [],
        "workflows": [],
        "pipelines": [],
        "declared": None,
    }
]


def _by_header(request: Request) -> SimpleNamespace:
    user = request.headers.get("x-user")
    if not user:
        raise HTTPException(401, "Not authenticated")
    return SimpleNamespace(id=user, email=f"{user}@example.com", name=user)


@pytest.fixture
def world(team, monkeypatch):
    """``root`` (platform admin); ``owner``, ``admin``, ``member``, ``viewer`` of
    ``org-1`` and its ``ws-1`` (org owners and admins hold the org-wide role);
    ``wanda``, an admin of ``ws-1`` alone; ``ws-2`` with nobody."""
    team.platform_admin("root")
    team.workspace("org-1", "ws-2")
    team.grant("wanda", "admin", "abi:org-1:ws-1")
    audit = MemoryAudit()
    directory = MemoryDirectory(
        [
            OrganizationScopes(
                "org-1", "EDF", (ScopeName("ws-1", "People"), ScopeName("ws-2", "Markets"))
            )
        ]
    )
    previous = runtime.configure(
        lambda: IamAdminService(EngineIamGateway(), audit, directory=directory)
    )

    async def gather():
        return MODULES

    monkeypatch.setattr(scopes, "gather", gather)
    app = FastAPI()
    app.include_router(router, prefix="/api/iam/admin")
    app.dependency_overrides[get_current_user_required] = _by_header
    yield SimpleNamespace(nexus=team, client=TestClient(app), audit=audit)
    runtime.configure(previous)


def get(world, path: str, user: str):
    return world.client.get(f"/api/iam/admin{path}", headers={"x-user": user})


def put(world, path: str, user: str, **body):
    return world.client.put(f"/api/iam/admin{path}", json=body, headers={"x-user": user})


def _columns(body) -> dict[str, dict]:
    org = body["organizations"][0]
    return {org["id"]: org, **{ws["id"]: ws for ws in org["workspaces"]}}


def test_the_platform_admin_reads_and_edits_every_set(world):
    resp = get(world, "/sets", "root")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["modules"] == MODULES
    assert "chat" in body["features"]
    columns = _columns(body)
    assert set(columns) == {"org-1", "ws-1", "ws-2"}
    assert all(c["editable"] for c in columns.values())
    assert columns["org-1"]["set"] == {"modules": None, "features": None}


def test_an_orgs_admins_edit_its_workspaces_sets_not_the_orgs(world):
    columns = _columns(get(world, "/sets?organization_id=org-1", "admin").json())

    assert columns["org-1"]["editable"] is False
    assert columns["ws-1"]["editable"] and columns["ws-2"]["editable"]
    assert put(world, "/sets/org-1", "admin", modules=["people"]).status_code == 403
    assert put(world, "/sets/org-1/workspaces/ws-1", "admin", modules=["people"]).status_code == 200


def test_a_workspace_admin_sees_its_workspaces_set_read_only(world):
    columns = _columns(get(world, "/sets?organization_id=org-1", "wanda").json())

    assert set(columns) == {"org-1", "ws-1"}
    assert columns["ws-1"]["editable"] is False
    # The org's own set is not theirs to read: the org is only the heading.
    assert columns["org-1"]["set"] is None
    assert put(world, "/sets/org-1/workspaces/ws-1", "wanda", modules=[]).status_code == 403


def test_an_orgs_set_the_caller_may_not_read_is_asked_once(world, monkeypatch):
    """Wanda administers both workspaces, not the org: the org's set is learned
    once, through the workspace that records none, and bounds the other too."""
    world.nexus.grant("wanda", "admin", "abi:org-1:ws-2")
    org = put(world, "/sets/org-1", "root", modules=["people"], features=["chat"])
    assert org.status_code == 200, org.text
    ws2 = put(world, "/sets/org-1/workspaces/ws-2", "root", modules=["agent/people/A"])
    assert ws2.status_code == 200, ws2.text
    calls: list[tuple[str, str]] = []
    iam_type = type(world.nexus.iam)
    asked = iam_type.effective_set

    def counted(self, org, workspace="-"):
        calls.append((org, workspace))
        return asked(self, org, workspace)

    monkeypatch.setattr(iam_type, "effective_set", counted)

    columns = _columns(get(world, "/sets?organization_id=org-1", "wanda").json())

    assert calls == [("org-1", "ws-1")]
    assert columns["ws-1"]["effective"] == {"modules": ["people"], "features": ["chat", "settings"]}
    assert columns["ws-2"]["effective"] == {
        "modules": ["agent/people/A"],
        "features": ["chat", "settings"],
    }


def test_who_reads_no_set_is_refused(world):
    for user in ("member", "viewer", "stranger"):
        assert get(world, "/sets?organization_id=org-1", user).status_code == 403, user
        assert get(world, "/sets", user).status_code == 403, user


def test_a_workspace_set_wider_than_its_orgs_is_refused_naming_the_extras(world):
    org = put(world, "/sets/org-1", "root", modules=["people", "market"], features=["chat"])
    assert org.status_code == 200, org.text
    # Settings always stays reachable.
    assert org.json()["set"] == {"modules": ["market", "people"], "features": ["chat", "settings"]}

    wider = put(
        world, "/sets/org-1/workspaces/ws-1", "admin", modules=["people", "crm"], features=["files"]
    )

    assert wider.status_code == 422
    assert "crm" in wider.json()["detail"] and "feature files" in wider.json()["detail"]
    narrower = put(world, "/sets/org-1/workspaces/ws-1", "admin", modules=["agent/people/A"])
    assert narrower.status_code == 200
    assert narrower.json()["effective"] == {
        "modules": ["agent/people/A"],
        "features": ["chat", "settings"],
    }


def test_narrowing_the_org_bounds_its_workspaces_at_once(world):
    put(world, "/sets/org-1", "root", modules=["people", "market"])
    put(world, "/sets/org-1/workspaces/ws-1", "admin", modules=["people", "market"])

    put(world, "/sets/org-1", "root", modules=["market"])

    ws = _columns(get(world, "/sets?organization_id=org-1", "admin").json())["ws-1"]
    assert ws["set"]["modules"] == ["market", "people"]
    assert ws["effective"]["modules"] == ["market"]


def test_every_change_is_audited_and_none_without_its_record(world):
    assert put(world, "/sets/org-1/workspaces/ws-1", "admin", features=["chat"]).status_code == 200
    phases = [(r.action.operation, r.action.resource_id, r.phase) for r in world.audit.records]
    assert phases == [
        ("put_set", "org-1/ws-1", "requested"),
        ("put_set", "org-1/ws-1", "succeeded"),
    ]
    refused = put(world, "/sets/org-1", "admin", modules=[])
    assert refused.status_code == 403
    assert world.audit.records[-1].phase == "failed"

    world.audit.broken = True
    assert put(world, "/sets/org-1/workspaces/ws-1", "admin", features=[]).status_code == 503
    with as_service_account("engine"):
        assert world.nexus.iam.get_set("org-1", "ws-1").features == ("chat", "settings")


def test_an_unknown_workspace_is_not_found(world):
    assert put(world, "/sets/org-1/workspaces/ws-9", "root", modules=[]).status_code == 404
    assert put(world, "/sets/org-9", "root", modules=[]).status_code == 404
