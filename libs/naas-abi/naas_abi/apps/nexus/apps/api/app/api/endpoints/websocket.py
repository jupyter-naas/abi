"""
WebSocket API endpoints for server-side broadcasting and presence queries.
"""

from fastapi import APIRouter
from naas_abi.apps.nexus.apps.api.app.services.websocket import (
    get_user_workspaces,
    get_workspace_presence,
    sio,
)
from pydantic import BaseModel

router = APIRouter(prefix="/websocket", tags=["websocket"])


class BroadcastMessage(BaseModel):
    workspace_id: str
    event: str
    data: dict


@router.post("/broadcast")
async def broadcast_to_workspace(message: BroadcastMessage):
    """
    Server-side broadcast to all users in a workspace.

    Useful for:
    - System notifications
    - Workspace-wide alerts
    - Admin messages
    """
    await sio.emit(message.event, message.data, room=f"workspace:{message.workspace_id}")

    return {"status": "broadcasted", "workspace_id": message.workspace_id}


@router.get("/presence/{workspace_id}")
async def get_presence(workspace_id: str):
    """Get list of users currently active in a workspace."""
    users = get_workspace_presence(workspace_id)

    return {"workspace_id": workspace_id, "users": users, "count": len(users)}


@router.get("/presence/user/{user_id}")
async def get_user_presence(user_id: str):
    """Get list of workspaces a user is currently viewing."""
    workspaces = get_user_workspaces(user_id)

    return {"user_id": user_id, "workspaces": workspaces, "count": len(workspaces)}
