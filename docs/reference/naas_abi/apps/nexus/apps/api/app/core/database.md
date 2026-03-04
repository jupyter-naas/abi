# database

## What it is
- Async PostgreSQL database module built on **SQLAlchemy 2.0** with an **asyncpg**-backed async engine.
- Provides:
  - ORM declarative base (`Base`)
  - Async engine/session factory
  - FastAPI session dependency (`get_db`)
  - Simple SQL-file migration runner (`init_db`)
  - Utility helpers (`table_exists`, `get_row_count`)

## Public API
- `KNOWN_TABLES: frozenset[str]`
  - Allowlist of table names permitted for `get_row_count()`.

- `class Base(DeclarativeBase)`
  - Declarative base class for ORM models.

- `async_engine`
  - SQLAlchemy async engine created from `settings.database_url`.

- `AsyncSessionLocal`
  - `async_sessionmaker` bound to `async_engine` producing `AsyncSession` instances.

- `async def get_db() -> AsyncGenerator[AsyncSession, None]`
  - Yields an `AsyncSession` (intended as a FastAPI dependency).
  - Commits after the caller finishes; rolls back on exception.

- `async def init_db() -> None`
  - Checks DB connectivity (up to 5 retries, 2s delay).
  - Runs `*.sql` migrations found in the `migrations/` directory (relative to this module).
  - Executes semicolon-terminated statements; skips lines that are empty or SQL comments (`--`).
  - Treats errors containing `"already exists"` or `"duplicate"` as idempotent and counts them as skipped.

- `async def table_exists(table_name: str) -> bool`
  - Returns whether `table_name` exists in the `public` schema.

- `async def get_row_count(table_name: str) -> int`
  - Returns `COUNT(*)` for a table, **only** if `table_name` is in `KNOWN_TABLES`.
  - Raises `ValueError` for unknown table names.

## Configuration/Dependencies
- Depends on `settings.database_url` from:
  - `naas_abi.apps.nexus.apps.api.app.core.config`
- SQLAlchemy async engine parameters:
  - `echo=False`
  - `pool_pre_ping=True`
  - `pool_size=10`
  - `max_overflow=20`
- Uses `sqlalchemy.text` for raw SQL execution.
- Prints the database URL at import time:
  - `print(f"Database URL: {settings.database_url}")`

## Usage
### FastAPI dependency (session per request)
```python
from fastapi import Depends, FastAPI
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

from naas_abi.apps.nexus.apps.api.app.core.database import get_db

app = FastAPI()

@app.get("/health/db")
async def db_health(db: AsyncSession = Depends(get_db)):
    result = await db.execute(text("SELECT 1"))
    return {"ok": bool(result.scalar())}
```

### Run migrations on startup
```python
from fastapi import FastAPI
from naas_abi.apps.nexus.apps.api.app.core.database import init_db

app = FastAPI()

@app.on_event("startup")
async def startup():
    await init_db()
```

### Table utilities
```python
import asyncio
from naas_abi.apps.nexus.apps.api.app.core.database import table_exists, get_row_count

async def main():
    if await table_exists("users"):
        print(await get_row_count("users"))

asyncio.run(main())
```

## Caveats
- **PostgreSQL-only** (assumes `public` schema and PostgreSQL error messages for idempotency detection).
- `get_row_count()` only works for tables in `KNOWN_TABLES` and interpolates the table name into SQL (mitigated by the allowlist).
- `init_db()` implements a basic SQL splitter: statements must end with `;` and complex SQL containing semicolons in strings/procedures may not parse as intended.
- Importing the module prints `settings.database_url` to stdout (potentially sensitive in logs).
