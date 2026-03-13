# org_seed

## What it is
Config-driven provisioning applied on startup to ensure core entities exist in the database:

- Users (create by email if missing)
- Organizations (upsert by slug) + organization members
- Workspaces (upsert by slug) + workspace members
- Optional: store generated bootstrap credentials in an external secret service

## Public API
- `apply_configuration_seeds(secret_service: Any | None = None) -> None`  
  Applies provisioning using `settings.users` and `settings.organizations`.
  - Creates users that do not exist (by normalized email).
  - Upserts organizations and workspaces (by slug).
  - Ensures membership records exist and updates their `role`.
  - If a new user is created with a generated password and configuration requests it, writes credentials to `secret_service`.

## Configuration/Dependencies
- **Configuration source**
  - `settings.users`: list of user seed configs (from `naas_abi.apps.nexus.apps.api.app.core.config.settings`)
  - `settings.organizations`: list of organization seed configs including members and nested workspaces
  - Uses:
    - `OrganizationSeedConfig`
    - `WorkspaceSeedConfig`

- **Database**
  - Async SQLAlchemy engine: `async_engine`
  - Models:
    - `UserModel`, `OrganizationModel`, `WorkspaceModel`
    - `OrganizationMemberModel`, `WorkspaceMemberModel`

- **Password handling**
  - Uses `bcrypt` to hash generated passwords for newly created users.
  - Generates password via `secrets.token_urlsafe(24)`.

- **Secret service (optional)**
  - Expected interface: `secret_service.set(key: str, value: str)`.
  - Keys written on new-user creation (when enabled by config):
    - `NEXUS_USER_<EMAIL_PREFIX>_EMAIL`
    - `NEXUS_USER_<EMAIL_PREFIX>_PASSWORD`
  - `<EMAIL_PREFIX>` is derived from normalized email uppercased, with non-`[A-Z0-9]` replaced by `_`.

## Usage
Minimal async invocation (assumes `settings` is already populated by your app’s configuration):

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.core.org_seed import apply_configuration_seeds

async def main():
    await apply_configuration_seeds(secret_service=None)

asyncio.run(main())
```

With a secret service (must provide `.set()`):

```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.core.org_seed import apply_configuration_seeds

class SecretService:
    def set(self, key: str, value: str) -> None:
        print(f"{key}={value!r}")

async def main():
    await apply_configuration_seeds(secret_service=SecretService())

asyncio.run(main())
```

## Caveats
- User updates are **not** applied to existing users: if a user with the email already exists, it logs and skips config-driven updates for that user.
- Organizations and workspaces are upserted by `slug`; their branding/theme fields are overwritten from config on each run.
- Workspace creation is skipped if an owner cannot be resolved (workspace `owner_email` or the organization owner user ID must resolve to an existing user).
- Generated passwords are only available once; if `store_credentials_in_secrets` is enabled but no `secret_service` is provided, a warning is logged and the password is not persisted anywhere by this module.
