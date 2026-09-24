"""Only a platform superadmin can enable or disable workspace drives.

The system drive exposes every tenant's files and the platform drive is shared
across workspaces, while anyone can create a workspace and own it. So a
workspace role is not enough to flip either flag.
"""

from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary import (
    workspaces__primary_adapter__FastAPI as ws_api,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import WorkspaceRecord


def _user(*, superadmin: bool) -> SimpleNamespace:
    return SimpleNamespace(id="user-1", is_superadmin=superadmin)


@pytest.fixture
def workspace_role(monkeypatch: pytest.MonkeyPatch):
    """Set the caller's role in ws-1 (None = not a member)."""
    state = {"role": None}

    async def require_access(user_id: str, workspace_id: str) -> str:
        if state["role"] is None:
            raise HTTPException(status_code=403, detail="You do not have access to this workspace")
        return state["role"]

    async def get_role(user_id: str, workspace_id: str) -> str | None:
        return state["role"]

    monkeypatch.setattr(ws_api, "require_workspace_access", require_access)
    monkeypatch.setattr(ws_api, "get_workspace_role", get_role)
    monkeypatch.setattr(ws_api, "_load_org_role_override", AsyncMock(return_value=None))
    return state


def _service() -> AsyncMock:
    service = AsyncMock()
    service.update_workspace.return_value = WorkspaceRecord(
        id="ws-1",
        name="Demo",
        slug="demo",
        owner_id="user-1",
        created_at=datetime.now(tz=UTC),
        updated_at=datetime.now(tz=UTC),
    )
    return service


async def _patch(user, service, **fields):
    return await ws_api.update_workspace(
        workspace_id="ws-1",
        updates=ws_api.WorkspaceUpdate(**fields),
        current_user=user,
        service=service,
        org_service=AsyncMock(),
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("flag", ["system_drive_enabled", "platform_drive_enabled"])
@pytest.mark.parametrize("value", [True, False])
async def test_a_workspace_owner_cannot_toggle_a_drive(workspace_role, flag, value) -> None:
    workspace_role["role"] = "owner"
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        await _patch(_user(superadmin=False), service, **{flag: value})

    assert exc_info.value.status_code == 403
    service.update_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_a_drive_flag_cannot_ride_along_with_other_settings(workspace_role) -> None:
    workspace_role["role"] = "owner"
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        await _patch(_user(superadmin=False), service, name="Renamed", system_drive_enabled=True)

    assert exc_info.value.status_code == 403
    service.update_workspace.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize("role", [None, "member", "owner"])
async def test_a_superadmin_can_toggle_a_drive_on_any_workspace(workspace_role, role) -> None:
    workspace_role["role"] = role
    service = _service()

    await _patch(_user(superadmin=True), service, system_drive_enabled=True)

    updates = service.update_workspace.await_args.kwargs["updates"]
    assert updates.system_drive_enabled is True


@pytest.mark.asyncio
async def test_other_settings_still_need_a_workspace_admin(workspace_role) -> None:
    workspace_role["role"] = None
    service = _service()

    with pytest.raises(HTTPException) as exc_info:
        await _patch(_user(superadmin=True), service, name="Renamed")

    assert exc_info.value.status_code == 403
    service.update_workspace.assert_not_called()


@pytest.mark.asyncio
async def test_a_workspace_owner_can_still_rename(workspace_role) -> None:
    workspace_role["role"] = "owner"
    service = _service()

    await _patch(_user(superadmin=False), service, name="Renamed")

    service.update_workspace.assert_awaited_once()
