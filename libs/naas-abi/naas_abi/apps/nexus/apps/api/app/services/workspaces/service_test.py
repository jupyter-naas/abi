from __future__ import annotations

from types import SimpleNamespace

import pytest
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspacePermissionError,
    WorkspaceService,
)


@pytest.mark.asyncio
async def test_the_role_is_the_one_iam_holds(team) -> None:
    service = WorkspaceService(adapter=SimpleNamespace())

    assert await service.get_workspace_role(user_id="member", workspace_id="ws-1") == "member"
    assert await service.get_workspace_role(user_id="stranger", workspace_id="ws-1") is None
    assert await service.get_workspace_role(user_id="member", workspace_id="ws-unknown") is None


@pytest.mark.asyncio
async def test_require_workspace_access_raises_when_missing_role(team) -> None:
    service = WorkspaceService(adapter=SimpleNamespace())

    with pytest.raises(WorkspacePermissionError):
        await service.require_workspace_access(user_id="stranger", workspace_id="ws-1")
