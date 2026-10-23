"""Only a platform superadmin can enable or disable workspace drives.

The system drive exposes every tenant's files and the platform drive is shared
across workspaces, while anyone can create a workspace and own it. So a
workspace role is not enough to flip either flag. The platform admin holds
admin on every workspace through IAM, so it needs no membership to flip one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord


@pytest.fixture(autouse=True)
def _team(team):
    team.user("root")
    team.platform_admin("root")
    return team


def _client(*, user: str, superadmin: bool = False):
    service = AsyncMock()
    service.update_workspace.return_value = WorkspaceRecord(
        id="ws-1",
        name="Demo",
        slug="demo",
        owner_id="owner",
        organization_id="org-1",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    service.get_workspace_role.return_value = "owner"
    org_service = AsyncMock()
    org_service.get_role_features.return_value = None
    app = FastAPI()
    app.include_router(ws_api.router, prefix="/api/workspaces")
    app.dependency_overrides[get_current_user_required] = lambda: User.model_construct(
        id=user, email="me@example.com", name="Me", is_superadmin=superadmin
    )
    app.dependency_overrides[ws_api.get_workspace_service] = lambda: service
    app.dependency_overrides[ws_api.get_organization_service] = lambda: org_service
    return TestClient(app, raise_server_exceptions=False), service


def _patch(client: TestClient, **fields):
    return client.patch("/api/workspaces/ws-1", json=fields)


@pytest.mark.parametrize("flag", ["system_drive_enabled", "platform_drive_enabled"])
@pytest.mark.parametrize("value", [True, False])
def test_a_workspace_owner_cannot_toggle_a_drive(flag, value) -> None:
    client, service = _client(user="owner")

    assert _patch(client, **{flag: value}).status_code == 403
    service.update_workspace.assert_not_called()


def test_a_drive_flag_cannot_ride_along_with_other_settings() -> None:
    client, service = _client(user="owner")

    assert _patch(client, name="Renamed", system_drive_enabled=True).status_code == 403
    service.update_workspace.assert_not_called()


def test_a_superadmin_can_toggle_a_drive_on_any_workspace() -> None:
    client, service = _client(user="root", superadmin=True)

    assert _patch(client, system_drive_enabled=True).status_code == 200
    updates = service.update_workspace.await_args.kwargs["updates"]
    assert updates.system_drive_enabled is True


def test_other_settings_still_need_a_workspace_admin() -> None:
    for user in ("member", "viewer", "stranger"):
        client, service = _client(user=user)

        assert _patch(client, name="Renamed").status_code in (403, 404), user
        service.update_workspace.assert_not_called()


def test_a_workspace_owner_can_still_rename() -> None:
    client, service = _client(user="owner")

    assert _patch(client, name="Renamed").status_code == 200
    service.update_workspace.assert_awaited_once()
