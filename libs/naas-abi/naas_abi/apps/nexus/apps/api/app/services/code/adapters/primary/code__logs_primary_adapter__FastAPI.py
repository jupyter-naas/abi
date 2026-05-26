"""Code logs WebSocket primary adapter."""

from __future__ import annotations

import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.secondary.opencode_http import (
    get_broadcast_logs_adapter,
)

logs_router = APIRouter()


async def _auth_ws(websocket: WebSocket, token: str) -> bool:
    async for db in get_db():
        service = AuthService(adapter=AuthSecondaryAdapterPostgres(db=db))
        user = await service.get_user_from_access_token(token)
        if user is None:
            await websocket.close(code=4001, reason="Unauthorized")
            return False
        return True
    return False


@logs_router.websocket("/ws")
async def logs_ws(
    websocket: WebSocket,
    token: str = Query(..., description="Bearer access token"),
) -> None:
    if not await _auth_ws(websocket, token):
        return
    await websocket.accept()

    adapter = get_broadcast_logs_adapter()
    queue = adapter.subscribe()

    try:
        for line in adapter.get_recent_lines():
            await websocket.send_text(line + "\r\n")

        while True:
            try:
                line = await asyncio.wait_for(queue.get(), timeout=20.0)
                await websocket.send_text(line + "\r\n")
            except TimeoutError:
                try:
                    await websocket.send_text("")
                except Exception:
                    break
    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        adapter.unsubscribe(queue)
