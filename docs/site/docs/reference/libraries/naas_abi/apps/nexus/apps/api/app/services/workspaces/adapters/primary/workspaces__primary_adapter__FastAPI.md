# `workspaces__primary_adapter__FastAPI`

## What it is
FastAPI primary adapter implementing HTTP endpoints for **workspaces**, **workspace members**, **inference servers**, and **workspace logo upload**. It exposes an `APIRouter` plus Pydantic schemas, and delegates business logic to `WorkspaceService` backed by a Postgres secondary adapter.

## Public API

### Router
- `router: fastapi.APIRouter`
  - Routes (all require `get_current_user_required` unless noted):
    - `GET ""` → `list_workspaces()`: List workspaces accessible to the current user; includes `current_user_role` and `feature_flags`.
    - `GET "/{workspace_id}"` → `get_workspace()`: Get workspace by ID (requires workspace access).
    - `GET "/slug/{slug}"` → `get_workspace_by_slug()`: Get workspace by slug (requires access to returned workspace).
    - `POST ""` → `create_workspace()`: Create a workspace owned by current user. Returns 400 if slug already exists.
    - `DELETE "/{workspace_id}"` → `delete_workspace()`: Delete workspace (owner only).
    - `PATCH "/{workspace_id}"` → `update_workspace()`: Update workspace settings (owner/admin only).
    - `GET "/{workspace_id}/stats"` → `get_workspace_stats()`: Get workspace stats (requires access).
    - `GET "/{workspace_id}/members"` → `list_workspace_members()`: List members (requires access).
    - `POST "/{workspace_id}/members/invite"` → `invite_workspace_member()`: Invite member by email (admin/owner only).
    - `DELETE "/{workspace_id}/members/{user_id}"` → `remove_workspace_member()`: Remove member (admin/owner only; cannot remove yourself).
    - `PATCH "/{workspace_id}/members/{user_id}"` → `update_workspace_member()`: Update member fields (admin/owner only). If updating `role` to a known value and no change occurred, returns 404.
    - `GET "/{workspace_id}/servers"` → `list_inference_servers()`: List inference servers (requires access).
    - `POST "/{workspace_id}/servers"` → `create_inference_server()`: Create inference server (admin/owner only). `api_key` is encrypted via `deprecated_encrypt` if provided.
    - `PATCH "/{workspace_id}/servers/{server_id}"` → `update_inference_server()`: Update inference server (admin/owner only). `api_key` handling:
      - omitted (`None`) → not changed
      - empty string → stored as `None`
      - non-empty → encrypted via `deprecated_encrypt`
    - `DELETE "/{workspace_id}/servers/{server_id}"` → `delete_inference_server()`: Delete inference server (admin/owner only).
    - `POST "/{workspace_id}/upload-logo"` → `upload_workspace_logo()`: Upload and set workspace logo (admin/owner only), stored under `/uploads/logos/...`.

### Dependency provider
- `get_workspace_service(db: AsyncSession = Depends(get_db)) -> WorkspaceService`
  - Constructs `WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))`.

### Schemas (Pydantic models)
- `Workspace`: Workspace response schema (includes `current_user_role` and `feature_flags`).
- `WorkspaceCreate`: Request schema for creating a workspace.
  - `slug` must match `^[a-z0-9][a-z0-9\-]*[a-z0-9]$`
- `WorkspaceUpdate`: Request schema for patching a workspace.
- `WorkspaceMember`: Response schema for members.
- `WorkspaceMemberInvite`: Request schema for inviting a member (`role` in `admin|member|viewer`).
- `InferenceServer`: Response schema for inference servers.
- `InferenceServerCreate`: Request schema for creating an inference server (`type` in `ollama|abi|vllm|llamacpp|custom`).
- `InferenceServerUpdate`: Request schema for patching an inference server.

### Internal helper
- `_to_schema(record: WorkspaceRecord, current_user_role: str | None) -> Workspace`
  - Converts a `WorkspaceRecord` to `Workspace` and computes `feature_flags` via `build_feature_flags(...)`.

## Configuration/Dependencies
- **FastAPI**: `APIRouter`, `Depends`, `File`, `UploadFile`, `HTTPException`.
- **Database**: `AsyncSession` via `get_db()`; service uses `WorkspaceSecondaryAdapterPostgres`.
- **Auth/ACL**:
  - `get_current_user_required`
  - `require_workspace_access(user_id, workspace_id)`
  - `get_workspace_role(user_id, workspace_id)`
- **Feature flags**: `build_feature_flags(...)` using `settings.feature_flags`.
- **API key encryption**: `deprecated_encrypt` (used for inference server `api_key`).
- **Logo upload storage**:
  - `UPLOAD_DIR = Path("uploads/logos")` (created at import time)
  - Allowed extensions: `{".png",".jpg",".jpeg",".gif",".webp",".svg"}`
  - Max size: `5MB`

## Usage

### Include the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.primary.workspaces__primary_adapter__FastAPI import router

app = FastAPI()
app.include_router(router, prefix="/workspaces", tags=["workspaces"])
```

### Example: upload a workspace logo (HTTP)
```python
import requests

workspace_id = "your-workspace-id"
token = "Bearer <access-token>"

with open("logo.png", "rb") as f:
    r = requests.post(
        f"http://localhost:8000/workspaces/{workspace_id}/upload-logo",
        headers={"Authorization": token},
        files={"file": ("logo.png", f, "image/png")},
    )
print(r.status_code, r.json())
```

## Caveats
- `UPLOAD_DIR.mkdir(...)` runs at import time; the process needs write permission to `uploads/logos`.
- Logo upload reads the entire file into memory (`await file.read()`); capped to 5MB by `MAX_FILE_SIZE`.
- Updating inference server `api_key` distinguishes:
  - `api_key` omitted (`null`) → no change
  - `api_key` set to `""` → clears stored key (sets `None`)
- `feature_flags` are computed per workspace using a role fallback of `"member"` when role is missing.
