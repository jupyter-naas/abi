from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspacePermissionError,
    WorkspaceService,
)


@pytest.mark.asyncio
async def test_get_workspace_role_delegates_to_adapter() -> None:
    adapter = SimpleNamespace(get_workspace_role=AsyncMock(return_value="member"))
    service = WorkspaceService(adapter=adapter)

    role = await service.get_workspace_role(user_id="user-1", workspace_id="ws-1")

    assert role == "member"
    adapter.get_workspace_role.assert_awaited_once_with(user_id="user-1", workspace_id="ws-1")


@pytest.mark.asyncio
async def test_require_workspace_access_raises_when_missing_role() -> None:
    adapter = SimpleNamespace(get_workspace_role=AsyncMock(return_value=None))
    service = WorkspaceService(adapter=adapter)

    with pytest.raises(WorkspacePermissionError):
        await service.require_workspace_access(user_id="user-1", workspace_id="ws-1")
