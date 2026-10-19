from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime


class _SessionContext:
    def __init__(self, session: dict):
        self._session = session

    async def __aenter__(self) -> dict:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.mark.asyncio
async def test_join_workspace_denies_unauthorized_user(monkeypatch) -> None:
    sessions = {"sid-1": {"user_id": "user-1", "workspaces": set()}}
    monkeypatch.setattr(runtime.sio, "session", lambda sid: _SessionContext(sessions[sid]))
    enter_room = Mock()
    emit = AsyncMock()
    require_access = AsyncMock(side_effect=HTTPException(status_code=403, detail="denied"))
    monkeypatch.setattr(runtime.sio, "enter_room", enter_room)
    monkeypatch.setattr(runtime.sio, "emit", emit)
    monkeypatch.setattr(runtime, "require_workspace_access", require_access)

    result = await runtime.join_workspace("sid-1", {"workspace_id": "ws-1"})

    assert result == {"error": "workspace access denied"}
    assert sessions["sid-1"]["workspaces"] == set()
    assert runtime.workspace_presence.get("ws-1") is None
    enter_room.assert_not_called()
    emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_join_workspace_allows_authorized_user(monkeypatch) -> None:
    sessions = {"sid-1": {"user_id": "user-1", "workspaces": set()}}
    monkeypatch.setattr(runtime.sio, "session", lambda sid: _SessionContext(sessions[sid]))
    enter_room = Mock()
    emit = AsyncMock()
    require_access = AsyncMock(return_value="member")
    monkeypatch.setattr(runtime.sio, "enter_room", enter_room)
    monkeypatch.setattr(runtime.sio, "emit", emit)
    monkeypatch.setattr(runtime, "require_workspace_access", require_access)

    runtime.workspace_presence.clear()
    runtime.user_workspaces.clear()
    result = await runtime.join_workspace("sid-1", {"workspace_id": "ws-1"})

    assert result["workspace_id"] == "ws-1"
    assert "user-1" in result["users"]
    assert sessions["sid-1"]["workspaces"] == {"ws-1"}
    assert runtime.workspace_presence["ws-1"] == {"user-1"}
    assert runtime.user_workspaces["user-1"] == {"ws-1"}
    enter_room.assert_called_once_with("sid-1", "workspace:ws-1")
    emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_typing_start_rejects_unjoined_workspace(monkeypatch) -> None:
    sessions = {"sid-1": {"user_id": "user-1", "workspaces": set()}}
    monkeypatch.setattr(runtime.sio, "session", lambda sid: _SessionContext(sessions[sid]))
    emit = AsyncMock()
    monkeypatch.setattr(runtime.sio, "emit", emit)

    result = await runtime.typing_start(
        "sid-1",
        {"workspace_id": "ws-1", "conversation_id": "conv-1"},
    )

    assert result == {"error": "workspace not joined"}
    emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_connect_refuses_a_link_and_a_scoped_token(monkeypatch) -> None:
    """A link sits in a page URL: it must not open the socket. (Every other kind
    of credential is checked in ``auth/credential_boundaries_test.py``.)"""
    from naas_abi.apps.nexus.apps.api.app.services.apps.app_html_access import (
        mint_app_html_access_token,
    )
    from naas_abi.apps.nexus.apps.api.app.services.auth import credentials
    from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
    from naas_abi_core.services.iam.IAMService import IAMService

    iam = IAMService(IAMStoreMemory())
    iam.bootstrap()
    monkeypatch.setattr(credentials, "IAM", lambda: iam)

    token, _ = mint_app_html_access_token(user_id="user-1")

    assert await runtime.connect("sid-1", {}, {"token": token}) is False
