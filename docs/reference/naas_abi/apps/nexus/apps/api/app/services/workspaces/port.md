# WorkspacePermissionPort

## What it is
- An abstract “port” (interface) defining async operations for workspace permissions and workspace-related management.
- Includes dataclass records and input DTOs for workspaces, members, users, stats, and inference servers.
- Intended to be implemented by an adapter (e.g., DB/repository/service client) in a hexagonal/clean architecture.

## Public API

### Data models (dataclasses)
- `WorkspaceRecord`: Workspace representation returned by queries.
  - Fields: `id`, `name`, `slug`, `owner_id`, `organization_id`, branding colors, logo fields, `created_at`, `updated_at`, organization logo fields.
- `WorkspaceCreateInput`: Required/optional fields to create a workspace (`name`, `slug`, `owner_id`, …).
- `WorkspaceUpdateInput`: Partial update fields for a workspace (all optional).
- `WorkspaceStatsRecord`: Workspace stats counters: `nodes`, `edges`, `conversations`, `agents`.
- `WorkspaceMemberRecord`: Member info for a workspace (`id`, `workspace_id`, `user_id`, `role`, optional profile fields, `created_at`).
- `UserRecord`: Minimal user identity (`id`, `email`).
- `InferenceServerRecord`: Inference server configuration linked to a workspace (`id`, `workspace_id`, `name`, `type`, `endpoint`, `enabled`, optional paths/keys, timestamps).
- `InferenceServerCreateInput`: Input to create an inference server (includes `id`, `workspace_id`, required server fields, optional config).
- `InferenceServerUpdateInput`: Partial update fields for an inference server (all optional).

### Interface (abstract base class)
`class WorkspacePermissionPort(ABC)` — implement all methods below (all are `async`):

#### Workspace access and lifecycle
- `get_workspace_role(user_id: str, workspace_id: str) -> str | None`
  - Return the user’s role in the workspace, or `None` if not applicable.
- `list_workspaces_for_user(user_id: str) -> list[WorkspaceRecord]`
  - List workspaces accessible by a user.
- `get_workspace_by_id(workspace_id: str) -> WorkspaceRecord | None`
  - Fetch workspace by ID.
- `get_workspace_by_slug(slug: str) -> WorkspaceRecord | None`
  - Fetch workspace by slug.
- `workspace_slug_exists(slug: str) -> bool`
  - Check whether a slug is already in use.
- `create_workspace(workspace: WorkspaceCreateInput) -> WorkspaceRecord`
  - Create a workspace and return the created record.
- `delete_workspace(workspace_id: str) -> bool`
  - Delete a workspace; returns success.
- `update_workspace(workspace_id: str, updates: WorkspaceUpdateInput) -> WorkspaceRecord | None`
  - Update a workspace; returns updated record or `None` if not found.
- `set_workspace_logo(workspace_id: str, logo_url: str) -> WorkspaceRecord | None`
  - Set/update workspace logo URL; returns updated record or `None`.

#### Workspace stats
- `get_workspace_stats(workspace_id: str) -> WorkspaceStatsRecord | None`
  - Return aggregate workspace stats or `None`.

#### Membership management
- `list_workspace_members(workspace_id: str) -> list[WorkspaceMemberRecord]`
  - List members of a workspace.
- `get_user_by_email(email: str) -> UserRecord | None`
  - Lookup a user by email.
- `is_workspace_member(workspace_id: str, user_id: str) -> bool`
  - Check membership.
- `add_workspace_member(workspace_id: str, user_id: str, role: str) -> WorkspaceMemberRecord`
  - Add a member with a role; returns membership record.
- `remove_workspace_member(workspace_id: str, user_id: str) -> bool`
  - Remove a member; returns success.
- `update_workspace_member_role(workspace_id: str, user_id: str, role: str) -> bool`
  - Change a member’s role; returns success.

#### Inference server management
- `list_inference_servers(workspace_id: str) -> list[InferenceServerRecord]`
  - List inference servers configured for a workspace.
- `create_inference_server(server: InferenceServerCreateInput) -> InferenceServerRecord`
  - Create an inference server.
- `update_inference_server(workspace_id: str, server_id: str, updates: InferenceServerUpdateInput) -> InferenceServerRecord | None`
  - Update an inference server; returns updated record or `None`.
- `delete_inference_server(workspace_id: str, server_id: str) -> bool`
  - Delete an inference server; returns success.

## Configuration/Dependencies
- Uses only standard library modules: `abc`, `dataclasses`, `datetime`, and `__future__.annotations`.
- No runtime configuration in this module; behavior is defined by implementers of `WorkspacePermissionPort`.

## Usage
Implement the port in an adapter, then inject/use it from application services.

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
    WorkspacePermissionPort, WorkspaceCreateInput, WorkspaceRecord
)

class InMemoryWorkspacePort(WorkspacePermissionPort):
    def __init__(self):
        self._workspaces: dict[str, WorkspaceRecord] = {}

    async def create_workspace(self, workspace: WorkspaceCreateInput) -> WorkspaceRecord:
        rec = WorkspaceRecord(
            id="w1",
            name=workspace.name,
            slug=workspace.slug,
            owner_id=workspace.owner_id,
            organization_id=workspace.organization_id,
        )
        self._workspaces[rec.id] = rec
        return rec

    async def get_workspace_by_id(self, workspace_id: str) -> WorkspaceRecord | None:
        return self._workspaces.get(workspace_id)

    # Implement all remaining abstract methods in real code...
    async def get_workspace_role(self, user_id: str, workspace_id: str) -> str | None: ...
    async def list_workspaces_for_user(self, user_id: str) -> list[WorkspaceRecord]: ...
    async def get_workspace_by_slug(self, slug: str) -> WorkspaceRecord | None: ...
    async def workspace_slug_exists(self, slug: str) -> bool: ...
    async def delete_workspace(self, workspace_id: str) -> bool: ...
    async def update_workspace(self, workspace_id: str, updates): ...
    async def get_workspace_stats(self, workspace_id: str): ...
    async def list_workspace_members(self, workspace_id: str): ...
    async def get_user_by_email(self, email: str): ...
    async def is_workspace_member(self, workspace_id: str, user_id: str) -> bool: ...
    async def add_workspace_member(self, workspace_id: str, user_id: str, role: str): ...
    async def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool: ...
    async def update_workspace_member_role(self, workspace_id: str, user_id: str, role: str) -> bool: ...
    async def list_inference_servers(self, workspace_id: str): ...
    async def create_inference_server(self, server): ...
    async def update_inference_server(self, workspace_id: str, server_id: str, updates): ...
    async def delete_inference_server(self, workspace_id: str, server_id: str) -> bool: ...
    async def set_workspace_logo(self, workspace_id: str, logo_url: str): ...

async def main():
    port = InMemoryWorkspacePort()
    created = await port.create_workspace(WorkspaceCreateInput(
        name="My Workspace",
        slug="my-workspace",
        owner_id="u1",
    ))
    fetched = await port.get_workspace_by_id(created.id)
    print(fetched)

asyncio.run(main())
```

## Caveats
- `WorkspacePermissionPort` is abstract; it cannot be instantiated directly.
- All methods are `async`; implementers must provide awaitable implementations.
- Default field values exist in some dataclasses (e.g., `primary_color="#22c55e"`, `enabled=True`), but validation/enforcement is not defined here.
