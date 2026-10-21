# WebSocketService

## What it is
- A small service wrapper around the websocket `runtime` module.
- Provides helpers to:
  - Broadcast events to all websocket clients in a workspace room.
  - Query presence information for a workspace or user.

## Public API
- `class WebSocketService`
  - `async broadcast_to_workspace(workspace_id: str, event: str, data: dict[str, Any]) -> dict[str, str]`
    - Emits `event` with `data` to the websocket room `workspace:{workspace_id}` via `runtime.sio.emit`.
    - Returns a simple status payload: `{"status": "broadcasted", "workspace_id": workspace_id}`.
  - `get_workspace_presence(workspace_id: str) -> list[str]`
    - Returns the presence list for a workspace via `runtime.get_workspace_presence(workspace_id)`.
  - `get_user_workspaces(user_id: str) -> list[str]`
    - Returns the list of workspaces associated with a user via `runtime.get_user_workspaces(user_id)`.

## Configuration/Dependencies
- Depends on `naas_abi.apps.nexus.apps.api.app.services.websocket.runtime`, specifically:
  - `runtime.sio.emit(...)` (an async socket server emitter)
  - `runtime.get_workspace_presence(workspace_id: str) -> list[str]`
  - `runtime.get_user_workspaces(user_id: str) -> list[str]`

## Usage
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.websocket.service import WebSocketService

async def main():
    ws = WebSocketService()
    result = await ws.broadcast_to_workspace(
        workspace_id="abc123",
        event="my_event",
        data={"message": "hello"},
    )
    print(result)

    print(ws.get_workspace_presence("abc123"))
    print(ws.get_user_workspaces("user-1"))

asyncio.run(main())
```

## Caveats
- `broadcast_to_workspace` is `async` and must be awaited.
- Broadcasting targets a room name formatted as `workspace:{workspace_id}`; clients must join that room to receive events.
