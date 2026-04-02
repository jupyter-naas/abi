from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.websocket.adapters.primary import (
    websocket__primary_adapter__FastAPI as websocket_api,
)


@pytest.mark.asyncio
async def test_broadcast_requires_workspace_access(monkeypatch) -> None:
    require_access = AsyncMock()
    broadcast = AsyncMock(return_value={"status": "broadcasted", "workspace_id": "ws-1"})
    monkeypatch.setattr(websocket_api, "require_workspace_access", require_access)
    monkeypatch.setattr(websocket_api.service, "broadcast_to_workspace", broadcast)

    result = await websocket_api.broadcast_to_workspace(
        websocket_api.BroadcastMessage(
            workspace_id="ws-1",
            event="workspace.alert",
            data={"ok": True},
        ),
        current_user=SimpleNamespace(id="user-1"),
    )

    assert result == {"status": "broadcasted", "workspace_id": "ws-1"}
    require_access.assert_awaited_once_with("user-1", "ws-1")
    broadcast.assert_awaited_once()


@pytest.mark.asyncio
async def test_presence_requires_workspace_access(monkeypatch) -> None:
    require_access = AsyncMock()
    monkeypatch.setattr(websocket_api, "require_workspace_access", require_access)
    monkeypatch.setattr(
        websocket_api.service, "get_workspace_presence", lambda _workspace_id: ["u1"]
    )

    result = await websocket_api.get_presence(
        workspace_id="ws-1",
        current_user=SimpleNamespace(id="user-1"),
    )

    assert result == {"workspace_id": "ws-1", "users": ["u1"], "count": 1}
    require_access.assert_awaited_once_with("user-1", "ws-1")


@pytest.mark.asyncio
async def test_user_presence_rejects_other_user() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await websocket_api.get_user_presence(
            user_id="user-2",
            current_user=SimpleNamespace(id="user-1"),
        )

    assert exc_info.value.status_code == 403


@pytest.mark.asyncio
async def test_user_presence_allows_current_user(monkeypatch) -> None:
    monkeypatch.setattr(
        websocket_api.service, "get_user_workspaces", lambda _user_id: ["ws-1", "ws-2"]
    )

    result = await websocket_api.get_user_presence(
        user_id="user-1",
        current_user=SimpleNamespace(id="user-1"),
    )

    assert result == {"user_id": "user-1", "workspaces": ["ws-1", "ws-2"], "count": 2}
