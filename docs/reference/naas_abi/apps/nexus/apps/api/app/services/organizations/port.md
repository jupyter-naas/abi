# OrganizationPermissionPort

## What it is
- A set of dataclasses that define the data shapes for organizations, members, workspaces, users, and domains.
- An abstract async port (`OrganizationPermissionPort`) that specifies the persistence/permission operations required by the Organizations service layer.

## Public API

### Data models (dataclasses)
- `OrganizationRecord`: Organization data returned by read operations.
- `OrganizationCreateInput`: Input payload for creating an organization.
- `OrganizationUpdateInput`: Partial update payload for updating an organization.
  - `set_fields: set[str] | None`: Optional field set hint for implementations.
- `OrganizationWorkspaceRecord`: Workspace representation tied to an organization/user listing.
- `OrganizationMemberRecord`: Organization membership record (including role).
- `UserRecord`: Minimal user record (id, email, optional name).
- `OrganizationDomainRecord`: Organization domain record including verification state.
- `OrganizationDomainCreateInput`: Input payload for creating a domain record.

### Port (abstract base class)
`class OrganizationPermissionPort(ABC)`: Implement this interface to provide organization-related data access and permission queries.

Methods (all `async`):
- `get_organization_role(user_id, org_id) -> str | None`: Return the user’s role in the organization, if any.
- `list_organizations_for_user(user_id) -> list[OrganizationRecord]`: List organizations visible/linked to the user.
- `get_organization_by_id(org_id) -> OrganizationRecord | None`: Fetch organization by ID.
- `get_organization_by_slug(slug) -> OrganizationRecord | None`: Fetch organization by slug.
- `organization_slug_exists(slug) -> bool`: Check if a slug is already used.
- `create_organization(organization: OrganizationCreateInput) -> OrganizationRecord`: Create a new organization.
- `update_organization(org_id, updates: OrganizationUpdateInput) -> OrganizationRecord | None`: Update an organization.
- `list_workspaces_for_org_and_user(org_id, user_id) -> list[OrganizationWorkspaceRecord]`: List workspaces for a given org-user context.
- `list_organization_members(org_id) -> list[OrganizationMemberRecord]`: List members of an organization.
- `get_user_by_email(email) -> UserRecord | None`: Lookup a user by email.
- `is_organization_member(org_id, user_id) -> bool`: Check membership.
- `add_organization_member(org_id, user_id, role, created_at) -> OrganizationMemberRecord`: Add a member to an organization.
- `get_organization_member(org_id, user_id) -> OrganizationMemberRecord | None`: Get a specific membership record.
- `update_organization_member_role(org_id, user_id, role) -> OrganizationMemberRecord | None`: Update a member’s role.
- `delete_organization_member(org_id, user_id) -> bool`: Remove a member.
- `list_organization_domains(org_id) -> list[OrganizationDomainRecord]`: List domains for an organization.
- `domain_exists(domain) -> bool`: Check if a domain is already registered.
- `create_organization_domain(domain: OrganizationDomainCreateInput) -> OrganizationDomainRecord`: Create a domain record.
- `get_organization_domain(org_id, domain_id) -> OrganizationDomainRecord | None`: Get a domain record by id.
- `verify_organization_domain(org_id, domain_id, verified_at) -> OrganizationDomainRecord | None`: Mark a domain as verified.
- `delete_organization_domain(org_id, domain_id) -> bool`: Delete a domain record.

## Configuration/Dependencies
- Uses only standard library modules:
  - `dataclasses.dataclass`
  - `datetime.datetime`
  - `abc.ABC`, `abc.abstractmethod`
- All port methods are asynchronous; callers should use an async runtime (e.g., `asyncio`).

## Usage

### Define records/inputs
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
)

org_in = OrganizationCreateInput(
    id="org_1",
    name="Acme",
    slug="acme",
    owner_id="user_1",
    created_at=datetime.utcnow(),
)
```

### Implement the port (minimal skeleton)
```python
from datetime import datetime
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationPermissionPort,
    OrganizationCreateInput,
    OrganizationRecord,
)

class InMemoryOrgPort(OrganizationPermissionPort):
    def __init__(self):
        self.orgs = {}

    async def create_organization(self, organization: OrganizationCreateInput) -> OrganizationRecord:
        rec = OrganizationRecord(**organization.__dict__)
        self.orgs[rec.id] = rec
        return rec

    # Implement all other abstract methods for a complete implementation...
    async def get_organization_role(self, user_id: str, org_id: str): ...
    async def list_organizations_for_user(self, user_id: str): ...
    async def get_organization_by_id(self, org_id: str): ...
    async def get_organization_by_slug(self, slug: str): ...
    async def organization_slug_exists(self, slug: str): ...
    async def update_organization(self, org_id: str, updates): ...
    async def list_workspaces_for_org_and_user(self, org_id: str, user_id: str): ...
    async def list_organization_members(self, org_id: str): ...
    async def get_user_by_email(self, email: str): ...
    async def is_organization_member(self, org_id: str, user_id: str): ...
    async def add_organization_member(self, org_id: str, user_id: str, role: str, created_at: datetime): ...
    async def get_organization_member(self, org_id: str, user_id: str): ...
    async def update_organization_member_role(self, org_id: str, user_id: str, role: str): ...
    async def delete_organization_member(self, org_id: str, user_id: str): ...
    async def list_organization_domains(self, org_id: str): ...
    async def domain_exists(self, domain: str): ...
    async def create_organization_domain(self, domain): ...
    async def get_organization_domain(self, org_id: str, domain_id: str): ...
    async def verify_organization_domain(self, org_id: str, domain_id: str, verified_at: datetime): ...
    async def delete_organization_domain(self, org_id: str, domain_id: str): ...
```

## Caveats
- `OrganizationPermissionPort` is abstract; any concrete implementation must implement **all** abstract methods.
- Methods are `async`; calling them requires `await` inside an async context.
- Many fields are optional (`None`) and may be unset; implementations should handle missing values consistently.
