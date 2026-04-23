# `OrganizationSecondaryAdapterPostgres`

## What it is
A Postgres/SQLAlchemy (async) secondary adapter implementing `OrganizationPermissionPort` for organization-related persistence and permission lookups (organizations, members, domains, and org workspaces).

## Public API

### Class: `OrganizationSecondaryAdapterPostgres`
- `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
  - Bind an `AsyncSession` directly (`db`) or lazily via `db_getter`.

#### Property
- `db -> AsyncSession`
  - Returns the bound session or raises `RuntimeError` if no session is available.

#### Organization permissions / roles
- `get_organization_role(user_id: str, org_id: str) -> str | None`
  - Returns member role if the user is an org member; returns `"owner"` if user matches `OrganizationModel.owner_id`; otherwise `None`.

#### Organizations
- `list_organizations_for_user(user_id: str) -> list[OrganizationRecord]`
  - Lists organizations where user is owner or member; ordered by organization name.
- `get_organization_by_id(org_id: str) -> OrganizationRecord | None`
  - Fetch by ID.
- `get_organization_by_slug(slug: str) -> OrganizationRecord | None`
  - Fetch by slug.
- `organization_slug_exists(slug: str) -> bool`
  - Checks whether an organization slug exists.
- `create_organization(organization: OrganizationCreateInput) -> OrganizationRecord`
  - Inserts an organization row and flushes.
- `update_organization(org_id: str, updates: OrganizationUpdateInput) -> OrganizationRecord | None`
  - Updates an organization and flushes.
  - If `updates.set_fields` is provided, only those fields are set (even if value is `None`).
  - Otherwise, only non-`None` values are applied.

#### Workspaces (scoped to org + user)
- `list_workspaces_for_org_and_user(org_id: str, user_id: str) -> list[OrganizationWorkspaceRecord]`
  - Lists workspaces in the org where user is owner or workspace member; ordered by workspace name.

#### Organization members
- `list_organization_members(org_id: str) -> list[OrganizationMemberRecord]`
  - Lists members (joined with user) ordered by membership creation time.
- `get_user_by_email(email: str) -> UserRecord | None`
  - Fetches a user by email.
- `is_organization_member(org_id: str, user_id: str) -> bool`
  - Checks membership existence.
- `add_organization_member(org_id: str, user_id: str, role: str, created_at: datetime) -> OrganizationMemberRecord`
  - Inserts a membership (UUID v4 id) and flushes; then looks up the user to include `email`/`name` in the returned record (may be `None` if user not found).
- `get_organization_member(org_id: str, user_id: str) -> OrganizationMemberRecord | None`
  - Fetches a membership; then looks up the user to attach `email`/`name` (may be `None`).
- `update_organization_member_role(org_id: str, user_id: str, role: str) -> OrganizationMemberRecord | None`
  - Updates role and flushes; returns the refreshed member record via `get_organization_member`.
- `delete_organization_member(org_id: str, user_id: str) -> bool`
  - Deletes membership row and flushes; returns `False` if not found.

#### Organization domains
- `list_organization_domains(org_id: str) -> list[OrganizationDomainRecord]`
  - Lists domains ordered by creation time.
- `domain_exists(domain: str) -> bool`
  - Checks whether a domain string exists.
- `create_organization_domain(domain: OrganizationDomainCreateInput) -> OrganizationDomainRecord`
  - Inserts a domain with `is_verified=False` and flushes.
- `get_organization_domain(org_id: str, domain_id: str) -> OrganizationDomainRecord | None`
  - Fetches a domain by `(org_id, domain_id)`.
- `verify_organization_domain(org_id: str, domain_id: str, verified_at: datetime) -> OrganizationDomainRecord | None`
  - Marks as verified, clears `verification_token`, sets `verified_at`, and flushes.
- `delete_organization_domain(org_id: str, domain_id: str) -> bool`
  - Deletes a domain row and flushes; returns `False` if not found.

## Configuration/Dependencies
- Requires an active `sqlalchemy.ext.asyncio.AsyncSession`.
- Uses SQLAlchemy models:
  - `OrganizationModel`, `OrganizationMemberModel`, `OrganizationDomainModel`
  - `WorkspaceModel`, `WorkspaceMemberModel`
  - `UserModel`
- Produces/consumes port-layer DTOs/records:
  - `OrganizationCreateInput`, `OrganizationUpdateInput`, `OrganizationDomainCreateInput`
  - `OrganizationRecord`, `OrganizationMemberRecord`, `OrganizationDomainRecord`, `OrganizationWorkspaceRecord`, `UserRecord`

## Usage

```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)

async def main(db: AsyncSession):
    adapter = OrganizationSecondaryAdapterPostgres(db=db)

    orgs = await adapter.list_organizations_for_user(user_id="user_123")
    print([o.slug for o in orgs])

    role = await adapter.get_organization_role(user_id="user_123", org_id="org_456")
    print(role)

# asyncio.run(main(db_session))
```

## Caveats
- If neither `db` nor `db_getter` yields a session, `db` access raises `RuntimeError`.
- Methods call `flush()` but do not `commit()`; transaction management is expected to be handled by the caller.
- `add_organization_member()` / `get_organization_member()` return `email`/`name` as `None` if the referenced user row is not found.
