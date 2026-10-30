from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import OrganizationSeedConfig
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord
from naas_abi_core.engine.call_context import as_service_account

NOW = datetime(2026, 1, 1)


@pytest.fixture(autouse=True)
def _team(team):
    return team


@pytest.fixture(autouse=True)
def _no_agent_seeding(monkeypatch):
    """The roster of a new workspace is the agents service's own tests'."""
    monkeypatch.setattr(ws_api, "seed_workspace_agents", AsyncMock())


def _client(*, user: str = "admin", storage=None, org_role: str | None = "admin"):
    service = AsyncMock()
    service.get_workspace.return_value = SimpleNamespace(id="ws-1", logo_url=None)
    service.update_workspace_logo.return_value = SimpleNamespace(id="ws-1")
    org_service = AsyncMock()
    org_service.get_organization_role.return_value = org_role
    org_service.get_role_features.return_value = None
    app = FastAPI()
    app.include_router(ws_api.router, prefix="/api/workspaces")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user, email="me@example.com", name="Me"
    )
    app.dependency_overrides[ws_api.get_workspace_service] = lambda: service
    app.dependency_overrides[ws_api.get_service_registry] = lambda: SimpleNamespace(agents=None)
    app.dependency_overrides[ws_api.get_organization_service] = lambda: org_service
    app.dependency_overrides[ws_api._get_object_storage] = lambda: storage or MemoryStorage()
    return TestClient(app, raise_server_exceptions=False), service


def test_only_org_owners_and_admins_create_workspaces_in_their_org(monkeypatch) -> None:
    monkeypatch.setattr(ws_api.placements, "place_new_workspace", AsyncMock())
    body = {"name": "Audit", "slug": "audit", "organization_id": "org-1"}

    for user in ("member", "viewer", "stranger"):
        client, service = _client(user=user)
        assert client.post("/api/workspaces", json=body).status_code == 403, user
        service.create_workspace.assert_not_called()

    for user in ("admin", "owner"):
        client, service = _client(user=user)
        client.post("/api/workspaces", json=body)
        service.create_workspace.assert_awaited_once()


def _record(**fields) -> WorkspaceRecord:
    return WorkspaceRecord(
        id="ws-1", name="Audit", slug="audit", owner_id="user-1", organization_id="org-1", **fields
    )


def test_the_create_form_chooses_no_feature(monkeypatch, team) -> None:
    """A new workspace grants nothing: who uses a feature or a module's agent is
    a policy's. A ``features`` field is not part of the request, and its
    catalog seed only installs."""
    monkeypatch.setattr(ws_api.placements, "place_new_workspace", AsyncMock())
    client, service = _client(user="admin")
    service.create_workspace.return_value = _record()
    before = {p.id for p in team.iam._all_policies()}

    resp = client.post(
        "/api/workspaces",
        json={
            "name": "Audit",
            "slug": "audit",
            "organization_id": "org-1",
            "features": ["chat", "graph"],
            "catalog_seed": {"agents": ["Abi"], "apps": ["naas_abi:kanban"]},
        },
    )

    assert resp.status_code == 200
    assert "features" not in ws_api.WorkspaceCreate.model_fields
    assert {p.id for p in team.iam._all_policies()} == before


def test_create_is_undone_when_placing_fails(monkeypatch, team) -> None:
    forget = AsyncMock(return_value=0)
    monkeypatch.setattr(
        ws_api.placements, "place_new_workspace", AsyncMock(side_effect=RuntimeError("nats"))
    )
    monkeypatch.setattr(ws_api.placements, "forget_workspace", forget)
    client, service = _client(user="admin")
    service.create_workspace.return_value = _record()

    resp = client.post(
        "/api/workspaces", json={"name": "Audit", "slug": "audit", "organization_id": "org-1"}
    )

    assert resp.status_code == 500
    forget.assert_awaited_once_with("ws-1")
    service.abandon_workspace.assert_awaited_once_with(_record())


@pytest.mark.asyncio
async def test_placements_of_an_undone_workspace_are_forgotten(team) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.iam import placements

    ws2 = team.workspace("org-1", "ws-2")
    with as_service_account("engine"):
        team.iam.put_placement("files", "drive/ws-1/*", workspace_container("org-1", "ws-1"))
        team.iam.put_placement("files", "drive/ws-2/*", ws2)

    assert await placements.forget_workspace("ws-1") == 1
    with as_service_account("engine"):
        assert [p.container for p in team.iam.list_placements("files")] == [ws2]


def test_configuration_lists_features_and_config_seeds(monkeypatch, team) -> None:
    client, service = _client(user="admin")
    service.get_workspace.return_value = _record()
    monkeypatch.setattr(
        ws_api.settings.feature_flags, "enabled_features", ["chat", "graph", "settings"]
    )
    seeds = [
        OrganizationSeedConfig.model_validate(
            {"name": "Acme", "slug": "acme", "workspaces": [{"slug": "audit", "apps": ["kanban"]}]}
        )
    ]
    monkeypatch.setattr(ws_api.settings, "organizations", seeds)

    resp = client.get("/api/workspaces/ws-1/configuration")

    assert resp.status_code == 200
    body = resp.json()
    # The deployment's: no set narrows them, a policy gives each.
    assert body["features"] == ["chat", "graph", "settings"]
    assert not {"feature_overrides", "pinned", "can_edit_features"} & set(body)
    assert body["seeds"] == [
        {
            "kind": "app",
            "value": "kanban",
            "source": "nexus_config.organizations[acme].workspaces[audit].apps[0]",
        }
    ]


def test_configuration_without_seed_is_empty(monkeypatch) -> None:
    client, service = _client(user="owner")
    service.get_workspace.return_value = _record()
    monkeypatch.setattr(ws_api.settings, "organizations", [])

    resp = client.get("/api/workspaces/ws-1/configuration")

    assert resp.status_code == 200
    assert resp.json()["seeds"] == []


def test_configuration_is_for_admins(monkeypatch) -> None:
    client, _ = _client(user="member")

    assert client.get("/api/workspaces/ws-1/configuration").status_code == 403


def test_logo_upload_goes_to_the_workspace_drive() -> None:
    storage = MemoryStorage()
    client, service = _client(storage=storage)

    resp = client.post(
        "/api/workspaces/ws-1/upload-logo", files={"file": ("logo.png", b"png", "image/png")}
    )

    assert resp.status_code == 200
    assert resp.json()["logo_url"].startswith("/api/workspaces/ws-1/logo?v=")
    assert storage.paths() == {"naas_abi/workspace-drive/ws-1/.settings/logos/logo.png"}
    service.update_workspace_logo.assert_awaited_once()

    served = client.get("/api/workspaces/ws-1/logo")
    assert served.status_code == 200
    assert served.headers["content-type"] == "image/png"
    assert served.content == b"png"


def test_only_workspace_admins_change_the_logo() -> None:
    storage = MemoryStorage()
    for user in ("member", "viewer"):
        client, service = _client(user=user, storage=storage)
        upload = client.post(
            "/api/workspaces/ws-1/upload-logo", files={"file": ("logo.png", b"png", "image/png")}
        )
        assert upload.status_code == 403, user
        assert client.delete("/api/workspaces/ws-1/logo").status_code == 403, user
        service.update_workspace_logo.assert_not_called()
    assert storage.paths() == set()


def test_svg_logos_are_served_sandboxed() -> None:
    storage = MemoryStorage()
    storage.put_object("naas_abi/workspace-drive/ws-1/.settings/logos", "logo.svg", b"<svg/>")
    client, _ = _client(storage=storage)

    served = client.get("/api/workspaces/ws-1/logo")

    assert served.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in served.headers["content-security-policy"]
    assert client.get("/api/workspaces/ws-2/logo").status_code == 404


def test_logo_route_rejects_ids_that_are_not_plain_ids() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
        is_safe_drive_id,
    )

    client, _ = _client()
    assert client.get("/api/workspaces/..%2E/logo").status_code == 404
    assert client.get("/api/workspaces/ws.1/logo").status_code == 404
    assert is_safe_drive_id("ws-319e131a833f")
    assert is_safe_drive_id("2f0c5d8e-uuid_like")
    assert not is_safe_drive_id("..")
    assert not is_safe_drive_id("a/b")
    assert not is_safe_drive_id("")


def test_workspace_description_is_limited_to_200_characters() -> None:
    import pytest
    from pydantic import ValidationError

    assert ws_api.WorkspaceUpdate(description="x" * 200).description == "x" * 200
    with pytest.raises(ValidationError):
        ws_api.WorkspaceUpdate(description="x" * 201)


def test_resources_are_what_the_caller_may_use_there(monkeypatch, team) -> None:
    """What IAM lets the caller use in the workspace: the features its policies
    grant, and each module with the items it may use (Settings: which pages it
    shows, General). An admin with no policy uses nothing."""
    from naas_abi.apps.nexus.apps.api.app.services.modules import scopes as module_scopes

    async def gathered(unavailable=None):
        return module_scopes.build(
            [
                module_scopes.Exposed("agent", "acme.people", "A"),
                module_scopes.Exposed("agent", "acme.people", "B"),
                module_scopes.Exposed("app", "acme.market", "prices"),
                module_scopes.Exposed("workflow", "acme.crm", "sync"),
            ]
        )

    monkeypatch.setattr(module_scopes, "gather", gathered)
    client, service = _client(user="admin")
    service.get_workspace.return_value = _record()

    body = client.get("/api/workspaces/ws-1/resources").json()
    assert body["modules"] == []

    team.allow(
        "admin",
        ["module:UseAgent", "module:OpenApp"],
        ["${scope}/module:agent/acme.people/A", "${scope}/module:app/acme.market/*"],
        "abi:nexus:organization/org-1/nexus:workspace/ws-1",
    )
    team.give_features(
        team.principal("admin"), ["chat"], "abi:nexus:organization/org-1/nexus:workspace/ws-1"
    )
    body = client.get("/api/workspaces/ws-1/resources").json()

    assert "chat" in body["features"]
    assert "can_edit_set" not in body
    assert body["modules"] == [
        {"module": "acme.market", "agents": 0, "apps": 1, "workflows": 0, "pipelines": 0},
        {"module": "acme.people", "agents": 1, "apps": 0, "workflows": 0, "pipelines": 0},
    ]
    assert body["totals"] == {"agents": 1, "apps": 1, "workflows": 0, "pipelines": 0}
    assert body["unavailable"] == []
    assert _client(user="member")[0].get("/api/workspaces/ws-1/resources").status_code == 403


def test_resources_name_the_kinds_a_source_did_not_answer_for(monkeypatch, team) -> None:
    """The jobs or discovery down: their kinds are named, so the settings never
    take a short count for "the workspace has none"."""
    from naas_abi.apps.nexus.apps.api.app.services.modules import scopes as module_scopes

    async def jobs_down(service=None):
        raise RuntimeError("no broker")

    async def no_apps():
        module_scopes._missing("apps")  # remote apps unreachable, in part
        return []

    monkeypatch.setattr(module_scopes, "engine_agents", lambda: [])
    monkeypatch.setattr(module_scopes, "remote_agents", lambda: [])
    monkeypatch.setattr(module_scopes, "apps", no_apps)
    monkeypatch.setattr(module_scopes, "workflows", jobs_down)
    monkeypatch.setattr(module_scopes, "declared_catalogs", lambda: [])
    monkeypatch.setattr(module_scopes, "engine_modules", lambda: [])
    client, service = _client(user="admin")
    service.get_workspace.return_value = _record()

    body = client.get("/api/workspaces/ws-1/resources").json()

    assert body["unavailable"] == ["apps", "pipelines", "workflows"]
    assert body["totals"] == {"agents": 0, "apps": 0, "workflows": 0, "pipelines": 0}
