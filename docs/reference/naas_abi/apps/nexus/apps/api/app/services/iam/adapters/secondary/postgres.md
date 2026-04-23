# IAMSecondaryAdapterPostgres

## What it is
- A PostgreSQL/SQLAlchemy (async) adapter implementing `IAMPolicyPort`.
- Provides IAM role and access-record lookups for workspaces, organizations, and conversations using the database models.

## Public API
- `class IAMSecondaryAdapterPostgres(IAMPolicyPort)`
  - `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
    - Binds the adapter to an `AsyncSession` directly (`db`) or via a lazy getter (`db_getter`).
  - `db -> AsyncSession` (property)
    - Returns the bound `AsyncSession`.
    - Raises `RuntimeError` if no session is available.
  - `async get_workspace_role(user_id: str, workspace_id: str) -> Role | None`
    - Returns the user’s role in the workspace from `WorkspaceMemberModel`.
    - Falls back to `"owner"` if `WorkspaceModel.owner_id == user_id`.
    - Returns `None` if no membership/ownership match is found.
  - `async get_organization_role(user_id: str, org_id: str) -> Role | None`
    - Returns the user’s role in the organization from `OrganizationMemberModel`.
    - Falls back to `"owner"` if `OrganizationModel.owner_id == user_id`.
    - Returns `None` if no membership/ownership match is found.
  - `async get_conversation_access_record(conversation_id: str) -> ConversationAccessRecord | None`
    - Loads `ConversationModel` by id.
    - Returns a `ConversationAccessRecord` with:
      - `conversation_id`
      - `workspace_id`
      - `owner_user_id` (from `ConversationModel.user_id`)
    - Returns `None` if the conversation is not found.

## Configuration/Dependencies
- Requires an active `sqlalchemy.ext.asyncio.AsyncSession`.
- Uses SQLAlchemy `select(...)` queries against:
  - `WorkspaceMemberModel`, `WorkspaceModel`
  - `OrganizationMemberModel`, `OrganizationModel`
  - `ConversationModel`
- Depends on IAM port types:
  - `IAMPolicyPort`, `Role`, `ConversationAccessRecord`

## Usage
```python
from sqlalchemy.ext.asyncio import AsyncSession
from naas_abi.apps.nexus.apps.api.app.services.iam.adapters.secondary.postgres import (
    IAMSecondaryAdapterPostgres,
)

async def check_access(db: AsyncSession, user_id: str, workspace_id: str):
    iam = IAMSecondaryAdapterPostgres(db=db)
    role = await iam.get_workspace_role(user_id=user_id, workspace_id=workspace_id)
    return role
```

## Caveats
- `db` property raises:
  - `RuntimeError("IAMSecondaryAdapterPostgres has no database binding")` if neither `db` nor `db_getter` is provided.
  - `RuntimeError("No database session bound in ServiceRegistry context")` if `db_getter()` returns `None`.
- Role fallback checks only ownership via `owner_id`; non-members/non-owners return `None`.
