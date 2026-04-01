from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from naas_abi.apps.nexus.apps.api.app.services.websocket.service import WebSocketService
from pydantic import BaseModel

router = APIRouter(prefix="/websocket", tags=["websocket"])
service = WebSocketService()


class BroadcastMessage(BaseModel):
    workspace_id: str
    event: str
    data: dict[str, Any]


@router.post("/broadcast")
async def broadcast_to_workspace(message: BroadcastMessage) -> dict[str, str]:
    return await service.broadcast_to_workspace(
        workspace_id=message.workspace_id,
        event=message.event,
        data=message.data,
    )


@router.get("/presence/{workspace_id}")
async def get_presence(workspace_id: str) -> dict[str, Any]:
    users = service.get_workspace_presence(workspace_id)
    return {
        "workspace_id": workspace_id,
        "users": users,
        "count": len(users),
    }


@router.get("/presence/user/{user_id}")
async def get_user_presence(user_id: str) -> dict[str, Any]:
    workspaces = service.get_user_workspaces(user_id)
    return {
        "user_id": user_id,
        "workspaces": workspaces,
        "count": len(workspaces),
    }


class WebSocketFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router
