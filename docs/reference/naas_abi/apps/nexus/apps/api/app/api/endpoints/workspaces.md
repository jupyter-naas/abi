# `workspaces` API endpoints

## What it is
FastAPI router providing authenticated endpoints to manage:
- Workspaces (CRUD + stats + branding/theme)
- Workspace members (list/invite/update role/remove)
- Workspace inference servers (CRUD)
- Workspace logo upload to local filesystem (`uploads/logos`)

All endpoints require authentication; workspace-scoped endpoints require workspace membership (and some require admin/owner role).

## Public API

### Router
- `router: fastapi.APIRouter` — routes defined in this module.

### Pydantic schemas
- `Workspace` — response model for workspaces (includes theme fields and optional inherited organization logos).
- `WorkspaceCreate` — request model for creating a workspace (`name`, `slug`, optional `organization_id` and theme fields).
- `WorkspaceUpdate` — request model for updating workspace branding/theme fields.
- `WorkspaceMember` — response model for workspace members (includes joined `email`/`name`).
- `WorkspaceMemberInvite` — request model for inviting an existing user by email and role.
- `InferenceServer` — response model for inference server configuration.
- `InferenceServerCreate` — request model for creating an inference server.
- `InferenceServerUpdate` — request model for updating an inference server.

### Endpoints (async)

#### Workspaces
- `GET "" -> list[Workspace]` (`list_workspaces`)
  - Lists workspaces the current user owns or is a member of.
  - Also preloads organization logos for convenience (`organization_logo_url`, `organization_logo_rectangle_url`).

- `GET "/{workspace_id}" -> Workspace` (`get_workspace`)
  - Returns a workspace by ID.
  - Requires workspace access; returns 404 if not found.

- `GET "/slug/{slug}" -> Workspace` (`get_workspace_by_slug`)
  - Returns a workspace by slug.
  - Requires workspace access; returns 404 if not found.

- `POST "" -> Workspace` (`create_workspace`)
  - Creates a new workspace; current user becomes owner and is added to `workspace_members` with role `"owner"`.
  - Enforces slug uniqueness (400 if slug exists).

- `DELETE "/{workspace_id}" -> dict[str,str]` (`delete_workspace`)
  - Deletes a workspace.
  - Only role `"owner"` can delete.

- `PATCH "/{workspace_id}" -> Workspace` (`update_workspace`)
  - Updates workspace fields provided in `WorkspaceUpdate`.
  - Requires role `"owner"` or `"admin"`.

- `GET "/{workspace_id}/stats" -> dict[str, Any]` (`get_workspace_stats`)
  - Returns counts for nodes, edges, conversations, and agents in the workspace.
  - Requires membership; 404 if workspace not found.

#### Workspace members
- `GET "/{workspace_id}/members" -> list[WorkspaceMember]` (`list_workspace_members`)
  - Lists members with joined user `email` and `name`.
  - Requires membership.

- `POST "/{workspace_id}/members/invite" -> dict[str,str]` (`invite_workspace_member`)
  - Adds an existing user (by email) to the workspace with the requested role (`admin|member|viewer`).
  - Requires current user role `"admin"` or `"owner"`.
  - 404 if user not found; 400 if already a member.

- `DELETE "/{workspace_id}/members/{user_id}" -> dict[str,str]` (`remove_workspace_member`)
  - Removes a user from the workspace.
  - Requires role `"admin"` or `"owner"`.
  - Cannot remove yourself (400).

- `PATCH "/{workspace_id}/members/{user_id}" -> dict[str,str]` (`update_workspace_member`)
  - Updates member role if `updates["role"]` is one of `admin|member|viewer`.
  - Requires role `"admin"` or `"owner"`.

#### Inference servers
- `GET "/{workspace_id}/servers" -> list[InferenceServer]` (`list_inference_servers`)
  - Lists all inference servers in the workspace.
  - Requires membership.

- `POST "/{workspace_id}/servers" -> InferenceServer` (`create_inference_server`)
  - Creates an inference server.
  - Requires role `"admin"` or `"owner"`.
  - Strips trailing `/` from `endpoint`.
  - Encrypts `api_key` via `_encrypt()` if provided.

- `PATCH "/{workspace_id}/servers/{server_id}" -> InferenceServer` (`update_inference_server`)
  - Updates an inference server.
  - Requires role `"admin"` or `"owner"`.
  - Strips trailing `/` from `endpoint`.
  - Encrypts `api_key` via `_encrypt()` when updated (or clears if empty string/falsey).

- `DELETE "/{workspace_id}/servers/{server_id}" -> dict` (`delete_inference_server`)
  - Deletes an inference server.
  - Requires role `"admin"` or `"owner"`.

#### Logo upload
- `POST "/{workspace_id}/upload-logo" -> dict` (`upload_workspace_logo`)
  - Uploads an image file to `uploads/logos/` and updates `workspace.logo_url` to `/uploads/logos/{filename}`.
  - Requires role `"admin"` or `"owner"`.
  - Validates extension (`.png .jpg .jpeg .gif .webp .svg`) and size (<= 5MB).
  - Deletes previous logo file if it was a local upload (`/uploads/logos/...`).

## Configuration/Dependencies
- **Authentication / authorization**
  - `get_current_user_required` (dependency) for all endpoints.
  - `require_workspace_access(user_id, workspace_id)` for membership enforcement.
  - `get_workspace_role(user_id, workspace_id)` for role checks.

- **Database**
  - `get_db` provides an `sqlalchemy.ext.asyncio.AsyncSession`.
  - Uses SQLAlchemy models: `WorkspaceModel`, `WorkspaceMemberModel`, `OrganizationModel`, `GraphNodeModel`, `GraphEdgeModel`, `ConversationModel`, `AgentConfigModel`, `UserModel`.
  - Inference servers use `InferenceServerModel` (imported inside functions).

- **Time**
  - Uses `UTC` from `naas_abi...datetime_compat`; timestamps are stored as naive datetimes (`datetime.now(UTC).replace(tzinfo=None)`).

- **File storage**
  - Writes uploaded logos under `uploads/logos` relative to current working directory:
    - `UPLOAD_DIR = Path("uploads/logos")` (created at import time).

## Usage

### Mount the router in a FastAPI app
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.api.endpoints import workspaces

app = FastAPI()
app.include_router(workspaces.router, prefix="/workspaces", tags=["workspaces"])
```

### Example request (logo upload)
```python
import requests

workspace_id = "ws-xxxxxxxxxxxx"
token = "YOUR_BEARER_TOKEN"

with open("logo.png", "rb") as f:
    r = requests.post(
        f"http://localhost:8000/workspaces/{workspace_id}/upload-logo",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("logo.png", f, "image/png")},
    )
print(r.status_code, r.json())
```

## Caveats
- `invite_workspace_member` does not create users; the invited email must already exist in `users`.
- `update_workspace_member` accepts an untyped `updates: dict`; only a valid `role` key triggers changes.
- Logo uploads assume something (e.g., nginx) serves `/uploads/...` URLs; this module only writes files locally.
- Upload validation is extension-based; content type is not validated beyond size and filename extension.
- Timestamps are stored without timezone info (naive datetime).
