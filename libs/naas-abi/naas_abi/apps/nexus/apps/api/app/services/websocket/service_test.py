from __future__ import annotations

from unittest.mock import AsyncMock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime
from naas_abi.apps.nexus.apps.api.app.services.websocket.service import WebSocketService


@pytest.mark.asyncio
async def test_broadcast_to_workspace_emits_event_to_workspace_room(monkeypatch) -> None:
    emit = AsyncMock()
    monkeypatch.setattr(runtime.sio, "emit", emit)
    service = WebSocketService()

    result = await service.broadcast_to_workspace(
        workspace_id="ws-1",
        event="workspace.alert",
        data={"message": "hello"},
    )

    assert result == {"status": "broadcasted", "workspace_id": "ws-1"}
    emit.assert_awaited_once_with(
        "workspace.alert",
        {"message": "hello"},
        room="workspace:ws-1",
    )


def test_get_workspace_presence_delegates_to_runtime(monkeypatch) -> None:
    def _fake_get_workspace_presence(workspace_id: str) -> list[str]:
        assert workspace_id == "ws-1"
        return ["user-1", "user-2"]

    monkeypatch.setattr(runtime, "get_workspace_presence", _fake_get_workspace_presence)
    service = WebSocketService()

    users = service.get_workspace_presence("ws-1")

    assert users == ["user-1", "user-2"]


def test_get_user_workspaces_delegates_to_runtime(monkeypatch) -> None:
    def _fake_get_user_workspaces(user_id: str) -> list[str]:
        assert user_id == "user-1"
        return ["ws-1", "ws-2"]

    monkeypatch.setattr(runtime, "get_user_workspaces", _fake_get_user_workspaces)
    service = WebSocketService()

    workspaces = service.get_user_workspaces("user-1")

    assert workspaces == ["ws-1", "ws-2"]
