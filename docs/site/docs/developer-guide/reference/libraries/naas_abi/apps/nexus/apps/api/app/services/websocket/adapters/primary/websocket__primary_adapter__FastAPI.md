# WebSocketFastAPIPrimaryAdapter

## What it is
- A FastAPI **primary adapter** exposing HTTP endpoints to:
  - Broadcast websocket events to a workspace.
  - Query websocket presence for a workspace or the current user.
- Provides an `APIRouter` mounted under `/websocket` with auth enforced via dependency injection.

## Public API
- **`BroadcastMessage` (pydantic.BaseModel)**
  - Request model for broadcasts.
  - Fields:
    - `workspace_id: str`
    - `event: str`
    - `data: dict[str, Any]`

- **`broadcast_to_workspace(message: BroadcastMessage, current_user: User) -> dict[str, str]`**
  - `POST /websocket/broadcast`
  - Validates the current user has access to `message.workspace_id`, then calls `WebSocketService.broadcast_to_workspace(...)`.

- **`get_presence(workspace_id: str, current_user: User) -> dict[str, Any]`**
  - `GET /websocket/presence/{workspace_id}`
  - Validates workspace access, then returns presence list from `WebSocketService.get_workspace_presence(workspace_id)` plus a count.

- **`get_user_presence(user_id: str, current_user: User) -> dict[str, Any]`**
  - `GET /websocket/presence/user/{user_id}`
  - Only allows querying **your own** presence; otherwise raises `HTTPException(403)`.
  - Returns workspaces from `WebSocketService.get_user_workspaces(user_id)` plus a count.

- **`WebSocketFastAPIPrimaryAdapter`**
  - Minimal wrapper exposing `self.router` for integration into a FastAPI app.

## Configuration/Dependencies
- **FastAPI dependencies**
  - Router enforces authentication globally via `Depends(get_current_user_required)`.
  - Each endpoint also injects `current_user: User = Depends(get_current_user_required)`.

- **Authorization**
  - Workspace access is enforced by `require_workspace_access(current_user.id, workspace_id)` for workspace-scoped endpoints.

- **Service**
  - Uses a module-level singleton `service = WebSocketService()`.

## Usage
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.websocket.adapters.primary.websocket__primary_adapter__FastAPI import (
    WebSocketFastAPIPrimaryAdapter,
)

app = FastAPI()
adapter = WebSocketFastAPIPrimaryAdapter()
app.include_router(adapter.router)
```

## Caveats
- `GET /websocket/presence/user/{user_id}` returns **403** unless `user_id` matches the authenticated user’s `id`.
- All routes require authentication due to the router-level dependency on `get_current_user_required`.
