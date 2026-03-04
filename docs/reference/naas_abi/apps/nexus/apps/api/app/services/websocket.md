# websocket (NEXUS real-time WebSocket service)

## What it is
A Socket.IO (ASGI) real-time service used by NEXUS to:
- Authenticate WebSocket clients via Bearer token
- Track user presence per workspace (in-memory)
- Broadcast workspace events (join/leave, typing, messages, cursor updates)
- Mount Socket.IO onto a FastAPI app via `init_websocket`

## Public API

### Module globals
- `sio: socketio.AsyncServer`
  - The Socket.IO server instance (ASGI mode) configured with CORS from `settings.cors_origins_list`.
- `workspace_presence: dict[str, set[str]]`
  - In-memory mapping: `workspace_id -> {user_id, ...}`.
- `user_workspaces: dict[str, set[str]]`
  - In-memory mapping: `user_id -> {workspace_id, ...}`.

### Socket.IO events (server handlers)
- `connect(sid, environ, auth) -> bool`
  - Authenticates the connection:
    - Accepts Bearer token from Socket.IO `auth` payload (`token`/`authorization`/`Authorization`) or `HTTP_AUTHORIZATION` header.
    - Validates token via `decode_token`.
    - Rejects revoked tokens via `is_access_token_revoked(jti)` when `jti` is present.
    - Stores `user_id` and a `workspaces` set in the Socket.IO session.
- `disconnect(sid) -> None`
  - Removes the user from all tracked workspaces and emits `user_left` to each workspace room (excluding the disconnecting socket).
  - Cleans up `user_workspaces` entry for the user.
- `join_workspace(sid, data) -> dict`
  - Requires `data["workspace_id"]`.
  - Joins room `workspace:{workspace_id}`.
  - Updates `workspace_presence` and `user_workspaces`.
  - Emits `user_joined` to the workspace room (excluding sender) with `timestamp`.
  - Returns current presence list: `{"workspace_id": ..., "users": [...]}`.
- `leave_workspace(sid, data) -> dict`
  - Requires `data["workspace_id"]`.
  - Leaves room `workspace:{workspace_id}`.
  - Updates presence tracking.
  - Emits `user_left` to the workspace room (excluding sender).
  - Returns `{"status": "left", "workspace_id": ...}`.
- `typing_start(sid, data) -> None`
  - Emits `user_typing` with `typing=True` to the workspace room (excluding sender).
- `typing_stop(sid, data) -> None`
  - Emits `user_typing` with `typing=False` to the workspace room (excluding sender).
- `message_created(sid, data) -> None`
  - Emits `new_message` to the workspace room (includes sender) with `timestamp`.
- `cursor_position(sid, data) -> None`
  - Emits `cursor_update` to the workspace room (excluding sender).

### Functions
- `get_workspace_presence(workspace_id: str) -> list[str]`
  - Returns the list of user IDs currently present in a workspace (from in-memory state).
- `get_user_workspaces(user_id: str) -> list[str]`
  - Returns the list of workspaces a user is currently viewing (from in-memory state).
- `init_websocket(app: fastapi.FastAPI) -> fastapi.FastAPI`
  - Mounts the Socket.IO ASGI app onto the provided FastAPI app.
  - Uses `settings.websocket_path` (default `"/ws/socket.io"`) to derive a mount prefix.
  - Ensures idempotent mounting via `app.state._nexus_socketio_mounted`.

## Configuration/Dependencies
- `settings.cors_origins_list`
  - Passed to `socketio.AsyncServer(cors_allowed_origins=...)`.
- `settings.websocket_path` (optional)
  - Path used to determine where to mount Socket.IO; default `"/ws/socket.io"`.
- Auth/revocation checks:
  - `decode_token(token)` (from `...api.endpoints.auth`)
  - `is_access_token_revoked(jti)` (from `...services.refresh_token`)
- Time handling:
  - `UTC` timezone from `...core.datetime_compat` used for ISO timestamps.

## Usage

### Mount into a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.websocket import init_websocket

app = FastAPI()
init_websocket(app)
```

### Client connection (token in auth payload)
```python
import socketio

sio = socketio.Client()
sio.connect(
    "http://localhost:8000",
    auth={"token": "Bearer <access_token>"},
)
sio.emit("join_workspace", {"workspace_id": "ws_123"})
```

## Caveats
- Presence tracking is **in-memory** (`workspace_presence`, `user_workspaces`):
  - Not shared across processes/instances.
  - Lost on restart.
- Event handlers generally assume `data` contains required keys (e.g., `workspace_id`); only `join_workspace`/`leave_workspace` explicitly return an error when missing `workspace_id`.
