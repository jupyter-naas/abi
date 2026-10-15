# `runtime` (NEXUS WebSocket Runtime)

## What it is
An in-process Socket.IO (ASGI) real-time service for NEXUS that:
- Authenticates Socket.IO connections using a Bearer token
- Tracks user presence per workspace (in-memory)
- Broadcasts workspace-scoped collaboration events (typing, messages, cursor)
- Supports a superadmin-only platform admin event stream room
- Mounts Socket.IO onto an existing FastAPI app

## Public API

### Module globals
- `sio: socketio.AsyncServer`  
  Socket.IO async server instance (ASGI mode). CORS origins are set in `init_websocket()`.

### FastAPI integration
- `init_websocket(app: fastapi.FastAPI) -> fastapi.FastAPI`  
  Mounts a `socketio.ASGIApp` onto the provided FastAPI app and configures Engine.IO CORS origins.

### Presence/query helpers
- `get_workspace_presence(workspace_id: str) -> list[str]`  
  Returns current user IDs present in a workspace (in-memory).
- `get_user_workspaces(user_id: str) -> list[str]`  
  Returns workspace IDs the user is currently viewing (in-memory).

### Socket.IO server event handlers
Registered via `@sio.event` (invoked by Socket.IO clients):

- `connect(sid, environ, auth)`  
  - Extracts Bearer token from `auth` (`token`/`authorization`/`Authorization`) or `HTTP_AUTHORIZATION` header.
  - Decodes token via `decode_token()`.
  - Rejects non-session tokens via `is_session_token(payload)`.
  - Rejects revoked tokens via `is_access_token_revoked(jti)`.
  - Loads `user.is_superadmin` from DB (best-effort) and stores in socket session.
  - Initializes socket session keys: `user_id`, `is_superadmin`, `workspaces` (a `set`).

- `disconnect(sid)`  
  - Removes user from all joined workspaces, updates presence maps.
  - Emits `user_left` to each workspace room (excluding the disconnecting socket).
  - Removes `user_workspaces[user_id]`.

- `join_workspace(sid, data)`  
  - Requires `data["workspace_id"]`.
  - Authorizes via `require_workspace_access(user_id, workspace_id)`; returns `{"error": "workspace access denied"}` on failure.
  - Joins room `workspace:{workspace_id}`.
  - Updates `workspace_presence` and `user_workspaces`.
  - Emits `user_joined` (with ISO timestamp) to the workspace room (excluding sender).
  - Returns `{"workspace_id": ..., "users": [...]}`.

- `leave_workspace(sid, data)`  
  - Requires `data["workspace_id"]`.
  - Leaves room and updates presence.
  - Emits `user_left` to the workspace room (excluding sender).
  - Returns `{"status": "left", "workspace_id": ...}`.

- `typing_start(sid, data)` / `typing_stop(sid, data)`  
  - Requires the socket to have joined the workspace (checks socket session membership).
  - Emits `user_typing` with `typing: True/False` to the workspace room (excluding sender).

- `message_created(sid, data)`  
  - Requires the socket to have joined the workspace.
  - Emits `new_message` (with ISO timestamp) to the workspace room (includes sender).

- `cursor_position(sid, data)`  
  - Requires the socket to have joined the workspace.
  - Emits `cursor_update` to the workspace room (excluding sender).

- `join_admin_events(sid, data=None)`  
  - Re-checks superadmin status from DB at join time (does not rely solely on cached flag).
  - If superadmin, joins `ADMIN_EVENTS_ROOM` and returns `{"status":"joined","room":...}`.
  - Otherwise returns `{"error":"superadmin required"}`.

- `leave_admin_events(sid, data=None)`  
  - Leaves `ADMIN_EVENTS_ROOM`, returns `{"status":"left","room":...}`.

## Configuration/Dependencies
- **Settings**
  - `settings.websocket_path` (default fallback: `"/ws/socket.io"`) used to compute the mount prefix.
  - `settings.frontend_url` used as default CORS origin if `app.state.abi_cors_origins` is not set.
- **CORS**
  - Engine.IO CORS origins are set to: `app.state.abi_cors_origins` if present, else `[settings.frontend_url]`.
  - Applied to `sio.eio.cors_allowed_origins`.
- **Authentication/Authorization**
  - `decode_token(token)` to decode the Bearer token.
  - `is_session_token(payload)` to enforce token scope.
  - `is_access_token_revoked(jti)` to reject revoked access tokens.
  - `require_workspace_access(user_id, workspace_id)` to authorize workspace access.
- **Database access (superadmin checks)**
  - `AsyncSessionLocal` and `AuthSecondaryAdapterPostgres.get_user_by_id()` are used to resolve `is_superadmin`.

## Usage

### Mount into a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime

app = FastAPI()
runtime.init_websocket(app)
```

### Event names (server expects/emits)
- Client emits: `join_workspace`, `leave_workspace`, `typing_start`, `typing_stop`, `message_created`, `cursor_position`, `join_admin_events`, `leave_admin_events`
- Server emits: `user_joined`, `user_left`, `user_typing`, `new_message`, `cursor_update`

## Caveats
- Presence tracking is **in-memory** (`workspace_presence`, `user_workspaces`): not shared across processes/workers and is lost on restart.
- Workspace-scoped events (`typing_*`, `message_created`, `cursor_position`) return `{"error": "workspace not joined"}` if the socket has not joined that workspace.
- Socket authentication is mandatory; missing/invalid/revoked/non-session tokens cause `connect` to return `False` (connection rejected).
- `join_workspace` calls `sio.enter_room(...)` without `await` (as written); behavior depends on the Socket.IO library’s implementation.
