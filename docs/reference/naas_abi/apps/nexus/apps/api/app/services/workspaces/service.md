# WorkspaceService

## What it is
An async service layer that manages workspaces, workspace membership, workspace stats, and workspace-scoped inference server records. It delegates persistence/lookup to a `WorkspacePermissionPort` adapter and raises typed errors for common validation/permission cases.

## Public API

### Exceptions
- `WorkspacePermissionError(workspace_id: str, user_id: str)`
  - Raised when a user has no role in the workspace (access denied).
  - `str(error) -> "workspace_access_denied"`
- `WorkspaceSlugAlreadyExistsError(slug: str)`
  - Raised when creating a workspace with an existing slug.
  - `str(error) -> f"workspace_slug_exists:{slug}"`
- `WorkspaceMemberAlreadyExistsError(workspace_id: str, user_id: str)`
  - Raised when inviting/adding a user who is already a member.
  - `str(error) -> "workspace_member_already_exists"`

### Class: `WorkspaceService`
Constructed with an adapter implementing `WorkspacePermissionPort`.

#### Workspace access/lookup
- `get_workspace_role(user_id: str, workspace_id: str) -> str | None`
  - Returns the user’s role in the workspace (or `None` if not a member).
- `require_workspace_access(user_id: str, workspace_id: str) -> str`
  - Returns role if present; otherwise raises `WorkspacePermissionError`.
- `list_workspaces(user_id: str) -> list[WorkspaceRecord]`
  - Lists workspaces visible/available to a user.
- `get_workspace(workspace_id: str) -> WorkspaceRecord | None`
  - Fetches workspace by ID.
- `get_workspace_by_slug(slug: str) -> WorkspaceRecord | None`
  - Fetches workspace by slug.
- `create_workspace(workspace: WorkspaceCreateInput) -> WorkspaceRecord`
  - Creates workspace; raises `WorkspaceSlugAlreadyExistsError` if slug exists.
- `delete_workspace(workspace_id: str) -> bool`
  - Deletes workspace by ID.
- `update_workspace(workspace_id: str, updates: WorkspaceUpdateInput) -> WorkspaceRecord | None`
  - Updates workspace fields.
- `get_workspace_stats(workspace_id: str) -> WorkspaceStatsRecord | None`
  - Retrieves workspace statistics record.
- `update_workspace_logo(workspace_id: str, logo_url: str) -> WorkspaceRecord | None`
  - Sets workspace logo URL.

#### Membership management
- `list_workspace_members(workspace_id: str) -> list[WorkspaceMemberRecord]`
  - Lists members for a workspace.
- `invite_workspace_member(workspace_id: str, email: str, role: str) -> WorkspaceMemberRecord | None`
  - Looks up user by email; returns `None` if user not found.
  - Raises `WorkspaceMemberAlreadyExistsError` if already a member.
  - Adds member with the provided role.
- `remove_workspace_member(workspace_id: str, user_id: str) -> bool`
  - Removes a member from a workspace.
- `update_workspace_member(workspace_id: str, user_id: str, updates: dict[str, Any]) -> bool`
  - Only supports `"role"` update.
  - Returns `False` if role not in `["admin", "member", "viewer"]`; otherwise updates role via adapter.

#### Inference server management (workspace-scoped)
- `list_inference_servers(workspace_id: str) -> list[InferenceServerRecord]`
  - Lists inference servers for a workspace.
- `create_inference_server(...)-> InferenceServerRecord`
  - Creates an inference server using `InferenceServerCreateInput`.
  - Generates `id` with `uuid4()`.
  - Strips trailing `/` from `endpoint`.
- `update_inference_server(...)-> InferenceServerRecord | None`
  - Updates an inference server using `InferenceServerUpdateInput`.
  - Strips trailing `/` from `endpoint` when provided.
- `delete_inference_server(workspace_id: str, server_id: str) -> bool`
  - Deletes an inference server by ID.

## Configuration/Dependencies
- Requires an adapter implementing `WorkspacePermissionPort` from:
  - `naas_abi.apps.nexus.apps.api.app.services.workspaces.port`
- Uses the following DTO/record types from the same module:
  - `WorkspaceCreateInput`, `WorkspaceUpdateInput`, `WorkspaceRecord`, `WorkspaceStatsRecord`
  - `WorkspaceMemberRecord`
  - `InferenceServerCreateInput`, `InferenceServerUpdateInput`, `InferenceServerRecord`
- Async: all service methods are `async` and must be awaited.

## Usage

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
    WorkspaceService,
    WorkspacePermissionError,
)

async def main(adapter, user_id: str, workspace_id: str):
    svc = WorkspaceService(adapter)

    try:
        role = await svc.require_workspace_access(user_id, workspace_id)
        print("role:", role)
    except WorkspacePermissionError:
        print("access denied")

    servers = await svc.list_inference_servers(workspace_id)
    print("servers:", servers)

# asyncio.run(main(adapter=..., user_id="u1", workspace_id="w1"))
```

## Caveats
- `update_workspace_member` ignores all fields except `"role"` and returns `False` for invalid roles instead of raising.
- `invite_workspace_member` returns `None` when the email does not map to an existing user.
- `create_inference_server` and `update_inference_server` normalize `endpoint` by removing trailing slashes.
