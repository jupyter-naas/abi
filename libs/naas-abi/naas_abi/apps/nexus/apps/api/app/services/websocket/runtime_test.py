from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.testing import NexusIam
from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime


class _SessionContext:
    def __init__(self, session: dict):
        self._session = session

    async def __aenter__(self) -> dict:
        return self._session

    async def __aexit__(self, exc_type, exc, tb) -> bool:
        return False


@pytest.fixture
def socket(monkeypatch):
    """A connected client per user: sessions by sid, rooms and emits recorded."""
    sessions: dict[str, dict] = {}
    monkeypatch.setattr(runtime.sio, "session", lambda sid: _SessionContext(sessions[sid]))
    enter_room = Mock()
    emit = AsyncMock()
    monkeypatch.setattr(runtime.sio, "enter_room", enter_room)
    monkeypatch.setattr(runtime.sio, "emit", emit)
    runtime.workspace_presence.clear()
    runtime.user_workspaces.clear()

    def connect(user_id: str) -> str:
        sid = f"sid-{user_id}"
        sessions[sid] = {"user_id": user_id, "workspaces": set(), "broadcast": set()}
        return sid

    return type(
        "Socket",
        (),
        {
            "sessions": sessions,
            "enter_room": enter_room,
            "emit": emit,
            "connect": staticmethod(connect),
        },
    )


@pytest.mark.asyncio
async def test_join_workspace_denies_a_stranger(team: NexusIam, socket) -> None:
    sid = socket.connect("stranger")

    result = await runtime.join_workspace(sid, {"workspace_id": "ws-1"})

    assert result == {"error": "workspace access denied"}
    assert socket.sessions[sid]["workspaces"] == set()
    assert runtime.workspace_presence.get("ws-1") is None
    socket.enter_room.assert_not_called()
    socket.emit.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("user", ["viewer", "member", "admin", "owner"])
async def test_join_workspace_allows_every_role(team: NexusIam, socket, user: str) -> None:
    sid = socket.connect(user)

    result = await runtime.join_workspace(sid, {"workspace_id": "ws-1"})

    assert result["workspace_id"] == "ws-1"
    assert user in result["users"]
    assert socket.sessions[sid]["workspaces"] == {"ws-1"}
    assert runtime.workspace_presence["ws-1"] == {user}
    assert runtime.user_workspaces[user] == {"ws-1"}
    socket.enter_room.assert_called_once_with(sid, "workspace:ws-1")
    socket.emit.assert_awaited_once()


@pytest.mark.asyncio
async def test_a_member_may_broadcast_in_a_joined_workspace(team: NexusIam, socket) -> None:
    sid = socket.connect("member")
    await runtime.join_workspace(sid, {"workspace_id": "ws-1"})
    socket.emit.reset_mock()
    data = {"workspace_id": "ws-1", "conversation_id": "conv-1", "message": "hi"}

    assert await runtime.typing_start(sid, data) is None
    assert await runtime.typing_stop(sid, data) is None
    assert await runtime.message_created(sid, data) is None
    assert await runtime.cursor_position(sid, {**data, "document_id": "d", "position": 3}) is None

    assert socket.emit.await_count == 4


@pytest.mark.asyncio
async def test_a_viewer_follows_a_workspace_but_sends_nothing_into_it(
    team: NexusIam, socket
) -> None:
    sid = socket.connect("viewer")
    await runtime.join_workspace(sid, {"workspace_id": "ws-1"})
    socket.emit.reset_mock()
    data = {"workspace_id": "ws-1", "conversation_id": "conv-1", "message": "hi"}

    results = [
        await runtime.typing_start(sid, data),
        await runtime.typing_stop(sid, data),
        await runtime.message_created(sid, data),
        await runtime.cursor_position(sid, {**data, "document_id": "d", "position": 3}),
    ]

    assert results == [{"error": "broadcast not allowed"}] * 4
    socket.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_typing_start_rejects_unjoined_workspace(team: NexusIam, socket) -> None:
    sid = socket.connect("member")

    result = await runtime.typing_start(
        sid,
        {"workspace_id": "ws-1", "conversation_id": "conv-1"},
    )

    assert result == {"error": "workspace not joined"}
    socket.emit.assert_not_awaited()


@pytest.mark.asyncio
async def test_leaving_a_workspace_drops_the_right_to_send_there(team: NexusIam, socket) -> None:
    sid = socket.connect("member")
    await runtime.join_workspace(sid, {"workspace_id": "ws-1"})

    await runtime.leave_workspace(sid, {"workspace_id": "ws-1"})

    assert socket.sessions[sid]["broadcast"] == set()


@pytest.mark.asyncio
async def test_the_admin_events_room_is_the_platform_administrators(team: NexusIam, socket) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.websocket.admin_events import (
        ADMIN_EVENTS_ROOM,
    )

    team.platform_admin("root")
    refused = {}
    for user in ("owner", "admin", "viewer", "stranger"):
        refused[user] = await runtime.join_admin_events(socket.connect(user))
    socket.enter_room.assert_not_called()
    assert all(r == {"error": "superadmin required"} for r in refused.values())

    sid = socket.connect("root")
    joined = await runtime.join_admin_events(sid)

    assert joined == {"status": "joined", "room": ADMIN_EVENTS_ROOM}
    socket.enter_room.assert_called_once_with(sid, ADMIN_EVENTS_ROOM)


@pytest.mark.asyncio
async def test_the_admin_events_room_follows_the_role_held_now(team: NexusIam, socket) -> None:
    sid = socket.connect("member")
    assert await runtime.join_admin_events(sid) == {"error": "superadmin required"}

    team.platform_admin("member")

    assert (await runtime.join_admin_events(sid))["status"] == "joined"


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
