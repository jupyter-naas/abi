# OrganizationService

## What it is
Async service layer for organization management (organizations, members, workspaces, and domains). It enforces a few business rules (e.g., slug uniqueness, membership checks) and delegates persistence/lookup operations to an injected `OrganizationPermissionPort` adapter.

## Public API

### Errors
- `OrganizationPermissionError(org_id: str, user_id: str)` (`PermissionError`)
  - Raised when a user has no role in an organization.
  - `str(error) -> "organization_access_denied"`.
- `OrganizationSlugAlreadyExistsError(slug: str)` (`ValueError`)
  - Raised when creating an organization with an existing slug.
  - `str(error) -> f"organization_slug_exists:{slug}"`.
- `OrganizationMemberAlreadyExistsError(org_id: str, user_id: str)` (`ValueError`)
  - Raised when inviting a user who is already a member.
  - `str(error) -> "organization_member_already_exists"`.
- `OrganizationDomainAlreadyExistsError(domain: str)` (`ValueError`)
  - Raised when adding a domain that already exists.
  - `str(error) -> "organization_domain_already_exists"`.

### Class: `OrganizationService`
Constructor:
- `OrganizationService(adapter: OrganizationPermissionPort)`
  - `adapter` implements the port methods used for data access.

Methods (all `async`):
- `get_organization_role(user_id: str, org_id: str) -> str | None`
  - Returns the user’s role in the organization, or `None`.
- `require_organization_access(user_id: str, org_id: str) -> str`
  - Returns role; raises `OrganizationPermissionError` if no access.
- `list_organizations(user_id: str) -> list[OrganizationRecord]`
  - Lists organizations available to the user.
- `get_organization(org_id: str) -> OrganizationRecord | None`
  - Fetches organization by id.
- `get_organization_by_slug(slug: str) -> OrganizationRecord | None`
  - Fetches organization by slug.
- `create_organization(..., now: datetime, ...) -> OrganizationRecord`
  - Creates an organization (generates `org-<12 hex chars>` id).
  - Enforces slug uniqueness; adds owner as a member with role `"owner"`.
  - Accepts numerous branding/login UI fields; `primary_color` defaults to `"#22c55e"`.
- `update_organization(org_id: str, updates: OrganizationUpdateInput) -> OrganizationRecord | None`
  - Updates an organization.
- `list_workspaces(org_id: str, user_id: str) -> list[OrganizationWorkspaceRecord]`
  - Lists workspaces for the org filtered by user.
- `list_members(org_id: str) -> list[OrganizationMemberRecord]`
  - Lists organization members.
- `invite_member(org_id: str, email: str, role: str, now: datetime) -> OrganizationMemberRecord | None`
  - Looks up user by email; returns `None` if not found.
  - Raises `OrganizationMemberAlreadyExistsError` if already a member.
  - Adds member with the provided role.
- `update_member_role(org_id: str, user_id: str, role: str) -> OrganizationMemberRecord | None`
  - Updates a member’s role.
- `remove_member(org_id: str, user_id: str) -> bool`
  - Removes a member unless they are missing or have role `"owner"`; returns `False` in those cases.
- `list_domains(org_id: str) -> list[OrganizationDomainRecord]`
  - Lists organization domains.
- `add_domain(org_id: str, domain: str, now: datetime, verification_token: str) -> OrganizationDomainRecord`
  - Enforces domain uniqueness; creates a domain record with a UUID id.
- `verify_domain(org_id: str, domain_id: str, verified_at: datetime) -> OrganizationDomainRecord | None`
  - Marks a domain as verified (delegated to adapter).
- `get_domain(org_id: str, domain_id: str) -> OrganizationDomainRecord | None`
  - Fetches a specific domain.
- `delete_domain(org_id: str, domain_id: str) -> bool`
  - Deletes a domain.

## Configuration/Dependencies
- Depends on an implementation of `OrganizationPermissionPort` (imported from `naas_abi.apps.nexus.apps.api.app.services.organizations.port`) providing:
  - Organization CRUD and queries (by id/slug, slug existence)
  - Membership operations (add/update/delete/get, membership check)
  - Workspace listing for org+user
  - Domain operations (list/create/verify/get/delete, domain existence)
  - User lookup by email
- Uses:
  - `uuid4()` for organization/domain ids
  - `datetime` timestamps passed in explicitly (`now`, `verified_at`)

## Usage
Minimal example showing access checks and slug conflict handling (adapter must be provided by your app):

```python
import asyncio
from datetime import datetime, timezone

# from naas_abi.apps.nexus.apps.api.app.services.organizations.service import (
#     OrganizationService, OrganizationSlugAlreadyExistsError
# )

async def main(adapter):
    svc = OrganizationService(adapter)
    now = datetime.now(timezone.utc)

    try:
        org = await svc.create_organization(
            name="Acme",
            slug="acme",
            owner_id="user-123",
            now=now,
        )
    except OrganizationSlugAlreadyExistsError as e:
        print(str(e))
        return

    role = await svc.require_organization_access(user_id="user-123", org_id=org.id)
    print("role:", role)

# asyncio.run(main(adapter))
```

## Caveats
- `create_organization` will always add the `owner_id` as a member with role `"owner"`.
- `remove_member` refuses to remove owners and returns `False` instead of raising.
- `invite_member` returns `None` (not an error) when the email does not match an existing user.
- Uniqueness checks are performed via adapter methods (`organization_slug_exists`, `domain_exists`); behavior depends on adapter correctness/consistency.
