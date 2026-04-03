from __future__ import annotations

from unittest.mock import AsyncMock

from app.services.websocket.adapters.primary import (
    websocket__primary_adapter__FastAPI as websocket_api,
)


class TestWebSocketHttpSecurity:
    async def test_broadcast_requires_authentication(self, client, test_workspace):
        response = await client.post(
            "/api/websocket/websocket/broadcast",
            json={
                "workspace_id": test_workspace["id"],
                "event": "workspace.alert",
                "data": {"message": "hello"},
            },
        )
        assert response.status_code == 401

    async def test_broadcast_denies_foreign_workspace(
        self,
        client,
        test_user,
        isolated_workspace,
        monkeypatch,
    ):
        emit_mock = AsyncMock(
            return_value={"status": "broadcasted", "workspace_id": isolated_workspace["id"]}
        )
        monkeypatch.setattr(websocket_api.service, "broadcast_to_workspace", emit_mock)

        response = await client.post(
            "/api/websocket/websocket/broadcast",
            json={
                "workspace_id": isolated_workspace["id"],
                "event": "workspace.alert",
                "data": {"message": "hello"},
            },
            headers=test_user["headers"],
        )
        assert response.status_code == 403
        emit_mock.assert_not_awaited()

    async def test_presence_requires_workspace_membership(
        self,
        client,
        test_user,
        isolated_workspace,
    ):
        response = await client.get(
            f"/api/websocket/websocket/presence/{isolated_workspace['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 403

    async def test_user_presence_allows_only_self(self, client, test_user, second_user):
        response = await client.get(
            f"/api/websocket/websocket/presence/user/{second_user['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 403

    async def test_user_presence_for_self_is_allowed(self, client, test_user, monkeypatch):
        monkeypatch.setattr(websocket_api.service, "get_user_workspaces", lambda _user_id: ["ws-1"])

        response = await client.get(
            f"/api/websocket/websocket/presence/user/{test_user['id']}",
            headers=test_user["headers"],
        )
        assert response.status_code == 200
        assert response.json()["user_id"] == test_user["id"]
