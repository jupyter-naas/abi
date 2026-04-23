# org_seed

## What it is
Config-driven provisioning executed on startup to ensure baseline records exist in the database:

- Users (create by email if missing)
- Organizations (upsert by slug)
- Organization members (ensure membership + role)
- Workspaces (upsert by slug)
- Workspace members (ensure membership + role)
- Optional mirroring of created user credentials into a Secret service

## Public API
- `apply_configuration_seeds(secret_service: Any | None = None) -> None`
  - Applies provisioning based on `settings.users` and `settings.organizations`.
  - Creates missing users; upserts organizations/workspaces; ensures membership rows and roles.
  - If `secret_service` is provided, may read/store credentials depending on user config.

> All other functions/constants in this module are internal helpers (prefixed with `_`).

## Configuration/Dependencies
- Configuration:
  - `settings.users`: list of user seed configs (from `naas_abi...core.config.settings`)
  - `settings.organizations`: list of organization seed configs, including:
    - `members`
    - `workspaces` (each including `members`)
- Database:
  - Uses `async_engine` and `AsyncSession` (`sqlalchemy.ext.asyncio`)
  - Writes to models: `UserModel`, `OrganizationModel`, `OrganizationMemberModel`, `WorkspaceModel`, `WorkspaceMemberModel`
- Password hashing:
  - Uses `bcrypt` for hashing generated/seeded passwords.
- Secret service (optional):
  - Any object implementing:
    - `get(key: str) -> Any`
    - `set(key: str, value: Any) -> None`
  - Keys used:
    - `NEXUS_USER_{EMAIL_PREFIX}_EMAIL`
    - `NEXUS_USER_{EMAIL_PREFIX}_PASSWORD`
  - `EMAIL_PREFIX` is derived from normalized email (uppercased; non `[A-Z0-9]` replaced with `_`).

## Usage
Minimal async usage (assuming `settings` is already populated by your app configuration):

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.core.org_seed import apply_configuration_seeds

async def main():
    await apply_configuration_seeds(secret_service=None)

asyncio.run(main())
```

With a compatible secret service:

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.core.org_seed import apply_configuration_seeds

class SecretService:
    def __init__(self):
        self._s = {}
    def get(self, k): return self._s.get(k)
    def set(self, k, v): self._s[k] = v

async def main():
    await apply_configuration_seeds(secret_service=SecretService())

asyncio.run(main())
```

## Caveats
- Existing users are **not updated** from config; if a user email already exists, the module logs and skips config-driven updates for that user.
- Organization/workspace branding fields are overwritten on upsert (owner is updated only if resolvable).
- Workspace creation is skipped if an owner cannot be resolved (from `workspace_cfg.owner_email` or the organization owner).
- Membership roles are enforced/updated; if the member is the resolved owner, role is set to `"owner"`.
- Timestamps are set using `datetime.now(UTC)` but stored as naive datetimes (`tzinfo=None`).
- Errors while applying a specific organization config are caught and logged; processing continues for other organizations.
