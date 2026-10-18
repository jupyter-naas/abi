# `ProvidersSecondaryAdapterPostgres`

## What it is
An async PostgreSQL-backed adapter implementing `ProviderAvailabilityPort` to:
- Retrieve workspace IDs for a user.
- Retrieve secret keys available across workspaces.
- Check which configuration keys exist in the process environment.

## Public API
- **Class: `ProvidersSecondaryAdapterPostgres(db: AsyncSession)`**
  - **`list_workspace_ids_for_user(user_id: str) -> list[str]`**
    - Returns workspace IDs from `WorkspaceMemberModel` rows matching `user_id`.
  - **`list_secret_keys_for_workspaces(workspace_ids: list[str]) -> set[str]`**
    - Returns distinct secret keys from `SecretModel` where `workspace_id` is in the provided list.
    - Returns an empty set when `workspace_ids` is empty.
  - **`list_environment_keys(key_names: list[str]) -> set[str]`**
    - Returns the subset of `key_names` that are present in `os.environ` (via `os.getenv` truthiness).

## Configuration/Dependencies
- **Database**
  - Requires an instantiated **`sqlalchemy.ext.asyncio.AsyncSession`**.
  - Uses SQLAlchemy `select(...)` queries.
- **Models**
  - `WorkspaceMemberModel` (expects `workspace_id`, `user_id` columns/attributes).
  - `SecretModel` (expects `key`, `workspace_id` columns/attributes).
- **Environment**
  - Reads environment variables via `os.getenv`.

## Usage
```python
import asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.secondary.providers__secondary_adapter__postgres import (
    ProvidersSecondaryAdapterPostgres,
)

async def main(db: AsyncSession, user_id: str):
    adapter = ProvidersSecondaryAdapterPostgres(db)

    workspace_ids = await adapter.list_workspace_ids_for_user(user_id)
    secret_keys = await adapter.list_secret_keys_for_workspaces(workspace_ids)
    env_keys = await adapter.list_environment_keys(["OPENAI_API_KEY", "DATABASE_URL"])

    print(workspace_ids, secret_keys, env_keys)

# asyncio.run(main(db_session, "user_123"))
```

## Caveats
- `list_environment_keys` includes a key only if `os.getenv(key)` is truthy; variables set to an empty string will be treated as absent.
- Database methods depend on the schema/ORM mapping of `WorkspaceMemberModel` and `SecretModel` and on a working async SQLAlchemy session.
