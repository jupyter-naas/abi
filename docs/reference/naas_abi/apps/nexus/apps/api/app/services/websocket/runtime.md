# `runtime` (NEXUS WebSocket Runtime)

## What it is
An in-process Socket.IO (ASGI) real-time service used by NEXUS to:
- Authenticate WebSocket connections via Bearer tokens
- Track user presence per workspace
- Broadcast workspace events (join/leave, typing, messages, cursor updates)
- Mount Socket.IO onto an existing FastAPI app

## Public API

### Module globals
- `sio: socketio.AsyncServer`  
  Socket.IO server configured for ASGI and runtime CORS (set during `init_websocket`).

### Presence/query helpers
- `get_workspace_presence(workspace_id: str) -> list[str]`  
  Returns current user IDs present in a workspace (in-memory).
- `get_user_workspaces(user_id: str) -> list[str]`  
  Returns workspace IDs currently associated with a user (in-memory).

### FastAPI integration
- `init_websocket(app: fastapi.FastAPI) -> fastapi.FastAPI`  
  Mounts the Socket.IO ASGI app onto the provided FastAPI app and configures CORS origins for Engine.IO.

### Socket.IO events (server-side handlers)
These are registered via `@sio.event` and invoked by Socket.IO clients:
- `connect(sid, environ, auth)`  
  Validates Bearer token (auth payload or `Authorization` header), checks token revocation, and initializes per-socket session (`user_id`, `workspaces` set).
- `disconnect(sid)`  
  Removes user from all joined workspaces, updates in-memory presence, and emits `user_left` to each workspace room.
- `join_workspace(sid, data)`  
  Requires `data["workspace_id"]`, checks access (`require_workspace_access`), joins room `workspace:{workspace_id}`, updates presence, emits `user_joined`, returns presence list.
- `leave_workspace(sid, data)`  
  Requires `data["workspace_id"]`, leaves room, updates presence, emits `user_left`, returns status.
- `typing_start(sid, data)` / `typing_stop(sid, data)`  
  Requires the socket to have joined the workspace; emits `user_typing` (typing True/False) to the workspace room (excluding sender).
- `message_created(sid, data)`  
  Requires the socket to have joined the workspace; emits `new_message` to the workspace room (includes timestamp).
- `cursor_position(sid, data)`  
  Requires the socket to have joined the workspace; emits `cursor_update` to the workspace room (excluding sender).

## Configuration/Dependencies
- **Authentication/authorization**
  - `decode_token(token)` to decode JWT-like payload.
  - `is_access_token_revoked(jti)` to deny revoked access tokens.
  - `require_workspace_access(user_id, workspace_id)` to authorize workspace membership.
- **Settings**
  - `settings.websocket_path` (default `"/ws/socket.io"`) influences mount prefix.
  - `settings.frontend_url` used as a fallback CORS origin.
- **CORS origins**
  - Read from `app.state.abi_cors_origins` if present, else `[settings.frontend_url]`.
  - Applied to `sio.eio.cors_allowed_origins`.

## Usage

### Mount into a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.websocket import runtime

app = FastAPI()
runtime.init_websocket(app)
```

### Client-side event names (overview)
After connecting with a Bearer token, a client can emit and listen to:
- Emit: `join_workspace`, `leave_workspace`, `typing_start`, `typing_stop`, `message_created`, `cursor_position`
- Listen: `user_joined`, `user_left`, `user_typing`, `new_message`, `cursor_update`

## Caveats
- Presence tracking is **in-memory** (`workspace_presence`, `user_workspaces`): it is not shared across processes and is lost on restart.
- Workspace-scoped events require the socket to have successfully joined the workspace; otherwise handlers may return `{"error": "workspace not joined"}`.
- Authentication is mandatory on connect; missing/invalid/revoked tokens cause the connection to be rejected (`connect` returns `False`).
