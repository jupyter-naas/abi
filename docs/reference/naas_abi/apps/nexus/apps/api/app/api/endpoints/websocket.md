# websocket (API endpoints)

## What it is
FastAPI endpoints for:
- Server-side broadcasting messages to all connected users in a workspace (via Socket.IO).
- Querying in-memory presence information for workspaces and users.

## Public API
- **`router`** (`fastapi.APIRouter`)
  - Mounted with prefix **`/websocket`**, tag **`websocket`**.

- **`BroadcastMessage`** (`pydantic.BaseModel`)
  - Request model for broadcasts:
    - `workspace_id: str`
    - `event: str`
    - `data: dict`

- **`broadcast_to_workspace(message: BroadcastMessage)`** (POST `/websocket/broadcast`)
  - Emits a Socket.IO event to room `workspace:{workspace_id}`.
  - Returns `{"status": "broadcasted", "workspace_id": ...}`.

- **`get_presence(workspace_id: str)`** (GET `/websocket/presence/{workspace_id}`)
  - Returns users currently active in the given workspace using `get_workspace_presence`.
  - Response includes `users` list and `count`.

- **`get_user_presence(user_id: str)`** (GET `/websocket/presence/user/{user_id}`)
  - Returns workspaces currently viewed by the given user using `get_user_workspaces`.
  - Response includes `workspaces` list and `count`.

## Configuration/Dependencies
- Depends on services from `naas_abi.apps.nexus.apps.api.app.services.websocket`:
  - **`sio`**: Socket.IO server instance providing `emit(...)`.
  - **`get_workspace_presence(workspace_id)`**: returns presence users for a workspace.
  - **`get_user_workspaces(user_id)`**: returns workspaces for a user.
- FastAPI routing via `APIRouter`.

## Usage
Minimal FastAPI app wiring:

```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints.websocket import router as websocket_router

app = FastAPI()
app.include_router(websocket_router)
```

Broadcast example (HTTP request body):

```python
import requests

requests.post(
    "http://localhost:8000/websocket/broadcast",
    json={
        "workspace_id": "ws_123",
        "event": "system:notification",
        "data": {"message": "Maintenance starts in 5 minutes"}
    },
).json()
```

Presence queries:

```python
import requests

requests.get("http://localhost:8000/websocket/presence/ws_123").json()
requests.get("http://localhost:8000/websocket/presence/user/user_456").json()
```

## Caveats
- Presence results and broadcasting behavior depend on the implementation/state maintained in `services.websocket` (not shown here).
- Broadcast targets the Socket.IO room named exactly `workspace:{workspace_id}`; clients must join that room for delivery.
