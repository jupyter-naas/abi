from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.avatar_store_test import MemoryStorage
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)

NOW = datetime(2026, 1, 1)


def _client(*, org_role: str | None = "member", ws_role: str = "admin", storage=None):
    service = AsyncMock()
    service.get_workspace.return_value = SimpleNamespace(id="ws-1", logo_url=None)
    service.update_workspace_logo.return_value = SimpleNamespace(id="ws-1")
    org_service = AsyncMock()
    org_service.get_organization_role.return_value = org_role
    app = FastAPI()
    app.include_router(ws_api.router, prefix="/api/workspaces")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id="user-1", email="me@example.com", name="Me"
    )
    app.dependency_overrides[ws_api.get_workspace_service] = lambda: service
    app.dependency_overrides[ws_api.get_organization_service] = lambda: org_service
    app.dependency_overrides[ws_api._get_object_storage] = lambda: storage or MemoryStorage()

    async def role(user_id: str, workspace_id: str) -> str:
        return ws_role

    return TestClient(app), service, role


def test_only_org_owners_and_admins_create_workspaces_in_their_org() -> None:
    client, service, _ = _client(org_role="member")

    resp = client.post(
        "/api/workspaces", json={"name": "Audit", "slug": "audit", "organization_id": "org-1"}
    )

    assert resp.status_code == 403
    service.create_workspace.assert_not_called()


def test_logo_upload_goes_to_the_workspace_drive(monkeypatch) -> None:
    storage = MemoryStorage()
    client, service, role = _client(storage=storage)
    monkeypatch.setattr(ws_api, "get_workspace_role", role)

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


def test_svg_logos_are_served_sandboxed(monkeypatch) -> None:
    storage = MemoryStorage()
    storage.put_object("naas_abi/workspace-drive/ws-1/.settings/logos", "logo.svg", b"<svg/>")
    client, _, _ = _client(storage=storage)

    served = client.get("/api/workspaces/ws-1/logo")

    assert served.headers["content-type"].startswith("image/svg+xml")
    assert "sandbox" in served.headers["content-security-policy"]
    assert client.get("/api/workspaces/ws-2/logo").status_code == 404


def test_logo_route_rejects_ids_that_are_not_plain_ids() -> None:
    from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
        is_safe_drive_id,
    )

    client, _, _ = _client()
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
