"""A workspace has no drive flags any more: IAM alone opens Platform Files and
System Files (the files API, ``GET /api/files/views``).

``platform_drive_enabled`` and ``system_drive_enabled`` are gone from the
workspace API: a PATCH still sending them (an older client) is ignored, never
stored, and the workspace says nothing about drives.
"""

from __future__ import annotations

from dataclasses import fields
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
    WorkspaceRecord,
    WorkspaceUpdateInput,
)

FLAGS = ("platform_drive_enabled", "system_drive_enabled")


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


@pytest.mark.parametrize("user,superadmin", [("owner", False), ("root", True)])
@pytest.mark.parametrize("flag", FLAGS)
def test_a_drive_flag_sent_in_a_patch_is_ignored(user, superadmin, flag) -> None:
    client, service = _client(user=user, superadmin=superadmin)

    response = _patch(client, name="Renamed", **{flag: True})

    assert response.status_code == 200
    updates = service.update_workspace.await_args.kwargs["updates"]
    assert updates.name == "Renamed"
    assert not hasattr(updates, flag)
    assert flag not in response.json()


def test_the_workspace_api_and_its_records_name_no_drive_flag() -> None:
    for flag in FLAGS:
        assert flag not in ws_api.Workspace.model_fields
        assert flag not in ws_api.WorkspaceUpdate.model_fields
        assert flag not in {f.name for f in fields(WorkspaceRecord)}
        assert flag not in {f.name for f in fields(WorkspaceUpdateInput)}
        assert flag not in WorkspaceModel.__table__.columns
    assert not hasattr(ws_api, "_DRIVE_FLAGS")


def test_other_settings_still_need_a_workspace_admin() -> None:
    for user in ("member", "viewer", "stranger"):
        client, service = _client(user=user)

        assert _patch(client, name="Renamed").status_code in (403, 404), user
        service.update_workspace.assert_not_called()


def test_a_workspace_owner_can_still_rename() -> None:
    client, service = _client(user="owner")

    assert _patch(client, name="Renamed").status_code == 200
    service.update_workspace.assert_awaited_once()
