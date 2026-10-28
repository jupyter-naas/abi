from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.primary import (
    organizations__primary_adapter__FastAPI as org_api,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationWorkspaceRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
    OrganizationService,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
from naas_abi_core.engine.call_context import as_service_account


@pytest.fixture(autouse=True)
def _team(team, monkeypatch):
    monkeypatch.setattr(org_api, "refresh_feature_policies", AsyncMock())
    return team


def _store() -> dict[str, OrganizationWorkspaceRecord]:
    return {
        ws.id: ws
        for ws in (
            OrganizationWorkspaceRecord(
                id="ws-1", name="AXA", slug="axa", owner_id="u", organization_id="org-1"
            ),
            OrganizationWorkspaceRecord(
                id="ws-2", name="EDF", slug="edf", owner_id="u", organization_id="org-1"
            ),
        )
    }


def _client(*, role: str, store: dict[str, OrganizationWorkspaceRecord]) -> TestClient:
    """``role``: the team member (``owner``, ``admin``, ``member``) who calls."""
    org_adapter = SimpleNamespace(
        db=None,
        get_organization_role_features=AsyncMock(return_value=None),
        get_organization_by_id=AsyncMock(return_value=None),
        list_workspaces_for_org=AsyncMock(side_effect=lambda org_id: list(store.values())),
    )

    async def _update(workspace_id, updates):
        store[workspace_id] = replace(
            store[workspace_id], workspace_group=updates.workspace_group.strip() or None
        )
        return store[workspace_id]

    ws_adapter = SimpleNamespace(update_workspace=AsyncMock(side_effect=_update))

    app = FastAPI()
    app.include_router(org_api.router, prefix="/organizations")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=role, email="admin@example.com", name="Admin"
    )
    app.dependency_overrides[org_api.get_organization_service] = lambda: OrganizationService(
        adapter=org_adapter
    )
    app.dependency_overrides[org_api.get_workspace_service_for_org_invite] = lambda: (
        WorkspaceService(adapter=ws_adapter)
    )
    return TestClient(app)


def test_bulk_update_sets_the_group_on_every_selected_workspace() -> None:
    store = _store()
    client = _client(role="admin", store=store)

    resp = client.post(
        "/organizations/org-1/workspaces/bulk-update",
        json={"workspace_ids": ["ws-1", "ws-2"], "workspace_group": " Key Accounts "},
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["updated"] == 2
    assert {ws["workspace_group"] for ws in resp.json()["workspaces"]} == {"Key Accounts"}


def test_bulk_update_refuses_members_and_foreign_workspaces() -> None:
    body = {"workspace_ids": ["ws-1"], "workspace_group": "X"}
    assert (
        _client(role="member", store=_store())
        .post("/organizations/org-1/workspaces/bulk-update", json=body)
        .status_code
        == 403
    )

    store = _store()
    resp = _client(role="owner", store=store).post(
        "/organizations/org-1/workspaces/bulk-update",
        json={"workspace_ids": ["ws-1", "ws-other"], "workspace_group": "X"},
    )
    assert resp.status_code == 400
    assert store["ws-1"].workspace_group is None


def test_the_listing_shows_each_workspaces_features_within_its_set(team) -> None:
    with as_service_account("engine"):
        team.iam.put_set("org-1", "ws-1", features=["chat", "graph", "settings"])

    resp = _client(role="admin", store=_store()).get("/organizations/org-1/workspaces")

    features = {ws["id"]: ws["features"] for ws in resp.json()}
    assert features["ws-1"] == ["chat", "graph", "settings"]
    assert "maps" in features["ws-2"]
    assert all("feature_overrides" not in ws for ws in resp.json())


def test_the_old_feature_overrides_route_is_gone() -> None:
    resp = _client(role="admin", store=_store()).put(
        "/organizations/org-1/workspaces/ws-1/features", json={"overrides": {}}
    )
    assert resp.status_code in (404, 405)


def test_workspace_features_lists_the_catalog_and_role_defaults() -> None:
    resp = _client(role="owner", store=_store()).get("/organizations/org-1/workspace-features")

    assert resp.status_code == 200
    body = resp.json()
    assert body["pinned"] == ["settings"]
    assert body["roles"] == ["owner", "admin", "member", "viewer"]
    assert "maps" in body["role_baseline"]["member"]
    assert "code" not in body["catalog"]
    # No set recorded: the org offers every feature of the catalog.
    assert body["available"] == body["catalog"]


def test_workspace_features_offer_what_the_orgs_set_has(team) -> None:
    with as_service_account("engine"):
        team.iam.put_set("org-1", features=["chat", "files"])

    body = (
        _client(role="owner", store=_store()).get("/organizations/org-1/workspace-features").json()
    )

    assert body["available"] == ["chat", "files"]


def test_listing_resolves_module_logo_paths(monkeypatch) -> None:
    monkeypatch.setattr(
        org_api,
        "resolve_stored_asset_url",
        lambda raw: f"https://api.example.com/modules/{raw}" if raw else raw,
    )
    store = _store()
    store["ws-1"] = replace(store["ws-1"], logo_url="src/external/axa/assets/public/axa-logo.png")

    resp = _client(role="admin", store=store).get("/organizations/org-1/workspaces")

    logos = {ws["slug"]: ws["logo_url"] for ws in resp.json()}
    assert (
        logos["axa"]
        == "https://api.example.com/modules/src/external/axa/assets/public/axa-logo.png"
    )
    assert logos["edf"] is None
