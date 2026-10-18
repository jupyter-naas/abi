# SecretsSecondaryAdapterPostgres

## What it is
- A PostgreSQL-backed (SQLAlchemy async) secondary adapter implementing `SecretsPersistencePort`.
- Persists and retrieves secrets stored as `SecretModel` rows, exposing them as `SecretRecord` objects.

## Public API
- `class SecretsSecondaryAdapterPostgres(SecretsPersistencePort)`
  - `__init__(db: AsyncSession | None = None, db_getter: Callable[[], AsyncSession | None] | None = None)`
    - Bind an `AsyncSession` directly (`db`) or defer binding via a getter (`db_getter`).
  - `db -> AsyncSession` (property)
    - Returns the bound session or raises if none is available.
  - `list_by_workspace(workspace_id: str) -> list[SecretRecord]`
    - List all secrets for a workspace, ordered by `key`.
  - `get_by_workspace_key(workspace_id: str, key: str) -> SecretRecord | None`
    - Fetch a single secret by `(workspace_id, key)`.
  - `get_by_id(secret_id: str) -> SecretRecord | None`
    - Fetch a single secret by `id`.
  - `create(record: SecretRecord) -> SecretRecord`
    - Insert a new `SecretModel` from the provided record and `flush()` the session.
  - `save(record: SecretRecord) -> None`
    - Update an existing row (matched by `record.id`); no-op if not found; `flush()`es.
    - Updates: `encrypted_value`, `description`, `category`, `updated_at`.
  - `delete(secret_id: str) -> bool`
    - Delete by `id`; returns `False` if not found, else deletes and returns `True`.
  - `commit() -> None`
    - Commit the current transaction.

## Configuration/Dependencies
- Depends on:
  - `sqlalchemy.ext.asyncio.AsyncSession`
  - `sqlalchemy.select`
  - `SecretModel` (SQLAlchemy model)
  - `SecretRecord`, `SecretsPersistencePort` (port/DTO types)
- Session binding:
  - Provide `db=AsyncSession` **or**
  - Provide `db_getter=Callable[[], AsyncSession | None]`
- Runtime errors:
  - If neither `db` nor `db_getter` is provided: `RuntimeError("SecretsSecondaryAdapterPostgres has no database binding")`
  - If `db_getter()` returns `None`: `RuntimeError("No database session bound in ServiceRegistry context")`

## Usage
```python
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.secondary.postgres import (
    SecretsSecondaryAdapterPostgres,
)

async def main():
    engine = create_async_engine("postgresql+asyncpg://user:pass@localhost:5432/db")
    Session = async_sessionmaker(engine, expire_on_commit=False)

    async with Session() as session:
        adapter = SecretsSecondaryAdapterPostgres(db=session)

        secrets = await adapter.list_by_workspace("ws_123")
        print(secrets)

        await adapter.commit()

asyncio.run(main())
```

## Caveats
- `create()` and `save()` call `flush()` but do **not** commit; call `commit()` explicitly to persist the transaction.
- `delete()` does not `flush()` or `commit()`; the deletion is finalized only after a commit (or other transaction handling) on the session.
