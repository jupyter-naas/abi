# WorkspaceSecondaryAdapterPostgres

## What it is
A PostgreSQL-backed secondary adapter implementing `WorkspacePermissionPort` using SQLAlchemy `AsyncSession`. It provides workspace, membership, and inference server persistence/query operations, plus basic role lookup.

## Public API

### Class: `WorkspaceSecondaryAdapterPostgres`
- `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
  - Bind a database session directly (`db`) or lazily via `db_getter`.

#### Properties
- `db -> AsyncSession`
  - Returns the bound `AsyncSession`.
  - Raises `RuntimeError` if no session is available.

#### Workspace roles
- `get_workspace_role(user_id: str, workspace_id: str) -> str | None`
  - Returns the user role if they are a member, otherwise returns `"owner"` if they own the workspace, else `None`.

#### Workspaces
- `list_workspaces_for_user(user_id: str) -> list[WorkspaceRecord]`
  - Lists workspaces where the user is owner or member, ordered by name; hydrates organization logo fields when applicable.
- `get_workspace_by_id(workspace_id: str) -> WorkspaceRecord | None`
  - Fetches a workspace by ID; hydrates organization logo fields when applicable.
- `get_workspace_by_slug(slug: str) -> WorkspaceRecord | None`
  - Fetches a workspace by slug; hydrates organization logo fields when applicable.
- `workspace_slug_exists(slug: str) -> bool`
  - Checks if a slug is already used.
- `create_workspace(workspace: WorkspaceCreateInput) -> WorkspaceRecord`
  - Creates a workspace and also inserts an `owner` membership record for the owner.
  - Generates workspace id as `ws-<12 hex chars>`.
- `update_workspace(workspace_id: str, updates: WorkspaceUpdateInput) -> WorkspaceRecord | None`
  - Updates non-`None` fields (name, logo/theme fields) and `updated_at`.
- `delete_workspace(workspace_id: str) -> bool`
  - Deletes the workspace if it exists.
- `set_workspace_logo(workspace_id: str, logo_url: str) -> WorkspaceRecord | None`
  - Updates `logo_url` and `updated_at` and persists the change.

#### Workspace stats
- `get_workspace_stats(workspace_id: str) -> WorkspaceStatsRecord | None`
  - Returns counts for:
    - graph nodes (`GraphNodeModel`)
    - graph edges (`GraphEdgeModel`)
    - conversations (`ConversationModel`)
    - agents (`AgentConfigModel`)
  - Returns `None` if workspace does not exist.

#### Members / users
- `list_workspace_members(workspace_id: str) -> list[WorkspaceMemberRecord]`
  - Returns members joined with user email/name, ordered by membership creation time (uses raw SQL).
- `get_user_by_email(email: str) -> UserRecord | None`
  - Looks up a user by email.
- `is_workspace_member(workspace_id: str, user_id: str) -> bool`
  - True if a membership exists for the user in the workspace.
- `add_workspace_member(workspace_id: str, user_id: str, role: str) -> WorkspaceMemberRecord`
  - Inserts a membership row and commits.
- `remove_workspace_member(workspace_id: str, user_id: str) -> bool`
  - Deletes a membership row and commits.
- `update_workspace_member_role(workspace_id: str, user_id: str, role: str) -> bool`
  - Updates role and commits.

#### Inference servers
- `list_inference_servers(workspace_id: str) -> list[InferenceServerRecord]`
  - Lists inference servers for a workspace ordered by `created_at` descending.
- `create_inference_server(server: InferenceServerCreateInput) -> InferenceServerRecord`
  - Inserts an inference server, commits, refreshes, and returns the record.
- `update_inference_server(workspace_id: str, server_id: str, updates: InferenceServerUpdateInput) -> InferenceServerRecord | None`
  - Updates non-`None` fields, commits, refreshes, and returns the record.
- `delete_inference_server(workspace_id: str, server_id: str) -> bool`
  - Deletes the inference server and commits.

## Configuration/Dependencies
- Requires a SQLAlchemy `AsyncSession` bound via:
  - `db=...`, or
  - `db_getter=...` returning an `AsyncSession` (must not return `None` at call time).
- Relies on SQLAlchemy ORM models:
  - `WorkspaceModel`, `WorkspaceMemberModel`, `UserModel`, `OrganizationModel`
  - `InferenceServerModel`
  - `GraphNodeModel`, `GraphEdgeModel`, `ConversationModel`, `AgentConfigModel`
- Uses `naas_abi...datetime_compat.UTC` to generate timestamps, stored as **naive** datetimes (`tzinfo` removed via `.replace(tzinfo=None)`).

## Usage

```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)

async def main(db: AsyncSession):
    adapter = WorkspaceSecondaryAdapterPostgres(db=db)

    workspaces = await adapter.list_workspaces_for_user(user_id="user-123")
    for ws in workspaces:
        print(ws.id, ws.name)

# asyncio.run(main(db_session))
```

## Caveats
- Transaction behavior is inconsistent across methods:
  - Some methods use `flush()` (e.g., `create_workspace`, `update_workspace`) and do **not** commit.
  - Others explicitly `commit()` (e.g., member and inference server mutations, `set_workspace_logo`).
  - Callers may need to manage commits/rollbacks depending on how the session is used.
- `list_workspace_members` uses raw SQL with table names `workspace_members` and `users`; schema/table naming must match exactly.
- Timestamps are stored as naive datetimes (timezone removed).
