# database

## What it is
- Async PostgreSQL database module using SQLAlchemy 2.0 (`AsyncSession`, `create_async_engine`).
- Provides:
  - ORM base class for models.
  - Async engine/session factory.
  - FastAPI session dependency.
  - Simple SQL-file migration runner on startup.
  - Utilities for checking table existence and row counts (restricted to known tables).

## Public API
- `KNOWN_TABLES: frozenset[str]`
  - Allowlist of table names used by `get_row_count()` for safety.
- `class Base(DeclarativeBase)`
  - Declarative base for ORM models.
- `async_engine`
  - Global SQLAlchemy async engine created from `settings.database_url`.
- `AsyncSessionLocal`
  - `async_sessionmaker` bound to `async_engine` (`expire_on_commit=False`).
- `async def get_db() -> AsyncGenerator[AsyncSession, None]`
  - Yields an `AsyncSession` (intended as a FastAPI dependency).
  - Commits after use; rolls back on exception.
- `async def init_db() -> None`
  - Verifies DB connectivity (up to 5 retries).
  - Runs `*.sql` migrations from `.../migrations`, executing parsed statements one-by-one.
  - Treats “already exists” / “duplicate” errors as idempotent and skips them.
- `async def table_exists(table_name: str) -> bool`
  - Checks `information_schema.tables` for a table in schema `public`.
- `async def get_row_count(table_name: str) -> int`
  - Returns `COUNT(*)` for an allowlisted table name.
  - Raises `ValueError` if `table_name` is not in `KNOWN_TABLES`.

## Configuration/Dependencies
- Configuration:
  - `settings.database_url` (imported from `naas_abi.apps.nexus.apps.api.app.core.config`).
- External dependencies:
  - `sqlalchemy` (async engine/session, `text`, ORM base).
  - A PostgreSQL-compatible async driver (URL is expected to be async; commonly `asyncpg`).
- Side effect on import:
  - Prints `Database URL: {settings.database_url}`.

## Usage
```python
import asyncio
from sqlalchemy import text

from naas_abi.apps.nexus.apps.api.app.core.database import (
    init_db,
    AsyncSessionLocal,
    table_exists,
    get_row_count,
)

async def main():
    await init_db()

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT 1"))
        print(result.scalar())

    print(await table_exists("users"))
    print(await get_row_count("users"))

asyncio.run(main())
```

## Caveats
- `init_db()` runs all `*.sql` migration files on every startup; idempotency relies on SQL and string-matching error messages containing “already exists” or “duplicate”.
- `get_row_count()` only accepts table names in `KNOWN_TABLES` and interpolates the table name into SQL (safe only because of the allowlist).
