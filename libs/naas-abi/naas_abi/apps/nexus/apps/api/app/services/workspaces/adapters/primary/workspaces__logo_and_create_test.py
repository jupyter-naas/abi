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
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord

NOW = datetime(2026, 1, 1)


@pytest.fixture(autouse=True)
def _team(team):
    return team


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


def test_create_saves_the_chosen_features(monkeypatch) -> None:
    monkeypatch.setattr(ws_api.placements, "place_new_workspace", AsyncMock())
    client, service = _client(user="admin")
    service.create_workspace.return_value = _record()
    service.set_workspace_feature_overrides.return_value = _record(
        feature_overrides={"maps": False, "graph": True}
    )

    resp = client.post(
        "/api/workspaces",
        json={
            "name": "Audit",
            "slug": "audit",
            "organization_id": "org-1",
            "feature_overrides": {"maps": False, "graph": True},
        },
    )

    assert resp.status_code == 200
    service.set_workspace_feature_overrides.assert_awaited_once_with(
        workspace_id="ws-1", overrides={"maps": False, "graph": True}
    )
    flags = resp.json()["feature_flags"]
    assert flags["maps"] is False and flags["graph"] is True


def test_create_without_features_keeps_the_role_defaults(monkeypatch) -> None:
    monkeypatch.setattr(ws_api.placements, "place_new_workspace", AsyncMock())
    client, service = _client(user="admin")
    service.create_workspace.return_value = _record()

    resp = client.post(
        "/api/workspaces", json={"name": "Audit", "slug": "audit", "organization_id": "org-1"}
    )

    assert resp.status_code == 200
    service.set_workspace_feature_overrides.assert_not_called()


def test_create_rejects_pinned_features_before_creating() -> None:
    client, service = _client(user="admin")

    resp = client.post(
        "/api/workspaces",
        json={
            "name": "Audit",
            "slug": "audit",
            "organization_id": "org-1",
            "feature_overrides": {"settings": False},
        },
    )

    assert resp.status_code == 400
    assert "settings" in resp.json()["detail"]
    service.create_workspace.assert_not_called()


def test_create_rejects_features_on_a_personal_workspace() -> None:
    client, service = _client(user="stranger", org_role=None)

    resp = client.post(
        "/api/workspaces",
        json={"name": "Mine", "slug": "mine", "feature_overrides": {"maps": True}},
    )

    assert resp.status_code == 400
    assert "organization" in resp.json()["detail"]
    service.create_workspace.assert_not_called()
    service.set_workspace_feature_overrides.assert_not_called()


def test_configuration_lists_features_and_config_seeds(monkeypatch) -> None:
    client, service = _client(user="admin")
    service.get_workspace.return_value = _record(feature_overrides={"maps": False})
    seeds = [
        OrganizationSeedConfig.model_validate(
            {"name": "Acme", "slug": "acme", "workspaces": [{"slug": "audit", "apps": ["kanban"]}]}
        )
    ]
    monkeypatch.setattr(ws_api.settings, "organizations", seeds)

    resp = client.get("/api/workspaces/ws-1/configuration")

    assert resp.status_code == 200
    body = resp.json()
    assert "maps" not in body["features"] and "chat" in body["features"]
    assert body["feature_overrides"] == {"maps": False}
    assert body["feature_overrides_source"] == "database"
    assert body["pinned"] == ["settings"]
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


def test_configuration_lets_org_admins_edit_features(monkeypatch) -> None:
    client, service = _client(user="admin")
    service.get_workspace.return_value = _record()

    body = client.get("/api/workspaces/ws-1/configuration").json()

    assert body["organization_id"] == "org-1"
    assert body["can_edit_features"] is True


def test_configuration_is_read_only_for_workspace_admins(monkeypatch) -> None:
    # A workspace admin who is only an org member sees the features read-only.
    client, service = _client(user="admin", org_role="member")
    service.get_workspace.return_value = _record()

    assert client.get("/api/workspaces/ws-1/configuration").json()["can_edit_features"] is False


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
