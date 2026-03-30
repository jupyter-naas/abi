from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime


class WebSocketService:
    async def broadcast_to_workspace(
        self,
        workspace_id: str,
        event: str,
        data: dict[str, Any],
    ) -> dict[str, str]:
        await runtime.sio.emit(
            event,
            data,
            room=f"workspace:{workspace_id}",
        )
        return {"status": "broadcasted", "workspace_id": workspace_id}

    def get_workspace_presence(self, workspace_id: str) -> list[str]:
        return runtime.get_workspace_presence(workspace_id)

    def get_user_workspaces(self, user_id: str) -> list[str]:
        return runtime.get_user_workspaces(user_id)
