"""
NEXUS Database Module

PostgreSQL-only async database with SQLAlchemy 2.0 ORM.
Uses asyncpg for production-grade performance.
"""

import re
from collections.abc import AsyncGenerator

from naas_abi.apps.nexus.apps.api.app.core.config import settings
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

# SQLite-only: rewrite Postgres-style `ADD COLUMN IF NOT EXISTS` (which SQLite
# rejects with a syntax error) to plain `ADD COLUMN`. The migration runner
# already catches the duplicate-column error on idempotent re-runs.
_SQLITE_ADD_COLUMN_RE = re.compile(
    r"\bADD\s+COLUMN\s+IF\s+NOT\s+EXISTS\b",
    re.IGNORECASE,
)

# Postgres lets you stack multiple ADD COLUMN clauses in one ALTER TABLE.
# SQLite requires one ALTER TABLE per column.
_ALTER_TABLE_PREFIX_RE = re.compile(
    r"^\s*(ALTER\s+TABLE\s+\S+)\s+(.*)$",
    re.IGNORECASE | re.DOTALL,
)
_ADD_COLUMN_SEP_RE = re.compile(
    r",\s*ADD\s+COLUMN\s+",
    re.IGNORECASE,
)

# SQLite has no equivalent for `COMMENT ON {COLUMN,TABLE} ...` — drop these
# silently on the SQLite path.
_COMMENT_ON_RE = re.compile(
    r"^\s*COMMENT\s+ON\s+",
    re.IGNORECASE,
)

# SQLite doesn't support `ALTER TABLE ... ALTER COLUMN ...` in any form
# (SET DEFAULT / DROP DEFAULT / SET NOT NULL / TYPE). For dev these are
# almost always cosmetic adjustments to defaults — drop them rather than
# fail or require a full table-rewrite.
_ALTER_COLUMN_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+\S+\s+ALTER\s+COLUMN\b",
    re.IGNORECASE,
)

# SQLite doesn't support `ALTER TABLE ... ADD/DROP CONSTRAINT ...` on
# existing tables (constraints can only be declared at CREATE TABLE time).
# Drop these on the SQLite path — they're a Postgres-only feature.
_ALTER_CONSTRAINT_RE = re.compile(
    r"^\s*ALTER\s+TABLE\s+\S+\s+(ADD|DROP)\s+CONSTRAINT\b",
    re.IGNORECASE,
)


def _adapt_statement_for_dialect(statement: str, dialect: str) -> list[str]:
    """Return the statement(s) to actually execute for the active dialect.

    Most migrations are dialect-agnostic, so this returns `[statement]`. For
    SQLite, two Postgres-isms get rewritten:
      - `ADD COLUMN IF NOT EXISTS` → `ADD COLUMN` (duplicate errors are
        caught and skipped by the runner for idempotent re-runs).
      - `ALTER TABLE t ADD COLUMN a, ADD COLUMN b` → two separate ALTERs.
    """
    if dialect != "sqlite":
        return [statement]

    # `COMMENT ON COLUMN/TABLE/...` is a no-op on SQLite — silently drop.
    if _COMMENT_ON_RE.match(statement):
        return []

    # `ALTER TABLE ... ALTER COLUMN ...` is unsupported on SQLite.
    if _ALTER_COLUMN_RE.match(statement):
        return []

    # `ALTER TABLE ... ADD/DROP CONSTRAINT ...` is unsupported on SQLite.
    if _ALTER_CONSTRAINT_RE.match(statement):
        return []

    rewritten = _SQLITE_ADD_COLUMN_RE.sub("ADD COLUMN", statement)

    # Detect "ALTER TABLE x ADD COLUMN ... , ADD COLUMN ..." and split.
    match = _ALTER_TABLE_PREFIX_RE.match(rewritten)
    if not match or "ADD COLUMN" not in match.group(2).upper():
        return [rewritten]

    prefix, body = match.group(1), match.group(2)
    parts = _ADD_COLUMN_SEP_RE.split(body)
    if len(parts) <= 1:
        return [rewritten]

    # `parts[0]` keeps its leading "ADD COLUMN " (the regex only splits on the
    # comma-separated ones), the rest lose it and need it re-added.
    statements = [f"{prefix} {parts[0].strip()}"]
    for tail in parts[1:]:
        statements.append(f"{prefix} ADD COLUMN {tail.strip()}")
    return statements

# Known tables for safe row count queries
KNOWN_TABLES = frozenset(
    {
        "users",
        "organizations",
        "organization_members",
        "workspaces",
        "workspace_members",
        "conversations",
        "messages",
        "chat_ingestion_jobs",
        "ontologies",
        "graph_nodes",
        "graph_edges",
        "api_keys",
        "provider_configs",
        "agent_configs",
        "app_configs",
        "secrets",
        "refresh_tokens",
        "revoked_tokens",
        "magic_link_tokens",
        "audit_logs",
        "rate_limit_events",
        "password_changes",
        "workspace_secrets",
        "model_catalog",
    }
)


# ============ ORM Base ============


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""

    pass


# ============ Async Engine & Session ============

print(f"Database URL: {settings.database_url}")

_is_sqlite = settings.database_url.startswith("sqlite")

_engine_kwargs: dict = {"echo": False, "pool_pre_ping": True}
if not _is_sqlite:
    # SQLite/aiosqlite uses SingletonThreadPool/NullPool and rejects these kwargs.
    _engine_kwargs["pool_size"] = 10
    _engine_kwargs["max_overflow"] = 20

async_engine = create_async_engine(settings.database_url, **_engine_kwargs)

AsyncSessionLocal = async_sessionmaker(
    async_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session.

    Usage in endpoints:
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
            result = await db.execute(select(User))
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Initialize the database schema (async). Runs all migrations on every startup."""
    import asyncio
    from pathlib import Path

    # Check database connection before attempting migrations
    print("Checking database connection...")
    max_retries = 5
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            async with async_engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
                print("✓ Database connection successful")
                break
        except Exception as e:
            if attempt < max_retries - 1:
                print(f"⚠ Database connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                print(f"  Retrying in {retry_delay}s...")
                await asyncio.sleep(retry_delay)
            else:
                print(f"✗ Database connection failed after {max_retries} attempts")
                print(f"  Error: {e}")
                if _is_sqlite:
                    hint = (
                        "Check that the SQLite file path in `database_url` is "
                        "writable and the parent directory exists."
                    )
                else:
                    hint = "Run 'make db-up' to start PostgreSQL."
                print(f"\n💡 Hint: {hint}")
                raise ConnectionError(f"Database not available. {hint}") from e

    migrations_dir = Path(__file__).parent.parent.parent / "migrations"

    # Run migrations in order
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        print("⚠ No migration files found")
        return

    print("Running migrations...")
    print(f"Found {len(migration_files)} migration(s)")

    current_dialect = "sqlite" if _is_sqlite else "postgresql"

    # Run each migration file in its own transaction
    for migration_file in migration_files:
        print(f"  • {migration_file.name}...", end=" ")
        sql = migration_file.read_text()

        # Honor `-- @dialect: <name>[, <name>...]` directive — file is skipped
        # if the current dialect is not in the list.
        allowed_dialects: set[str] | None = None
        for line in sql.split("\n"):
            stripped = line.strip()
            if stripped.lower().startswith("-- @dialect:"):
                allowed_dialects = {
                    d.strip().lower()
                    for d in stripped.split(":", 1)[1].split(",")
                    if d.strip()
                }
                break
        if allowed_dialects is not None and current_dialect not in allowed_dialects:
            print(f"⊘ (skipped on {current_dialect})")
            continue

        # Split by semicolon but handle multi-line statements
        statements = []
        current_statement = []

        for line in sql.split("\n"):
            line = line.strip()
            # Skip comments and empty lines
            if line.startswith("--") or not line:
                continue
            # Remove inline comments
            if "--" in line:
                line = line[: line.index("--")].strip()
            if line:
                current_statement.append(line)
                if line.endswith(";"):
                    statements.append(" ".join(current_statement))
                    current_statement = []

        # Execute each statement in its own transaction for idempotency
        executed = 0
        skipped = 0
        for raw_statement in statements:
            adapted = _adapt_statement_for_dialect(
                raw_statement.strip().rstrip(";"), current_dialect
            )
            for statement in adapted:
                if not statement:
                    continue
                try:
                    async with async_engine.begin() as conn:
                        await conn.execute(text(statement))
                        executed += 1
                except Exception as e:
                    error_msg = str(e).lower()
                    # Idempotent reruns: existing column / table / index
                    # surfaces as different wording across drivers.
                    if (
                        "already exists" in error_msg
                        or "duplicate" in error_msg
                        or "duplicate column" in error_msg
                    ):
                        skipped += 1
                    else:
                        print(f"\n✗ Error executing: {statement[:80]}...")
                        print(f"  Error: {e}")
                        raise

        # Report result
        if executed > 0 and skipped > 0:
            print(f"✓ ({executed} applied, {skipped} skipped)")
        elif executed > 0:
            print(f"✓ ({executed} applied)")
        elif skipped > 0:
            print("⊘ (already applied)")
        else:
            print("⊘ (empty)")

    print("✓ Migrations complete")


async def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    async with async_engine.begin() as conn:
        if _is_sqlite:
            result = await conn.execute(
                text(
                    "SELECT 1 FROM sqlite_master "
                    "WHERE type = 'table' AND name = :name"
                ),
                {"name": table_name},
            )
            return result.scalar() is not None
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables
                    WHERE table_schema = 'public'
                    AND table_name = :name
                )
            """),
            {"name": table_name},
        )
        return result.scalar() or False


async def get_row_count(table_name: str) -> int:
    """Get the number of rows in a table."""
    if table_name not in KNOWN_TABLES:
        raise ValueError(f"Unknown table: {table_name}. Allowed: {KNOWN_TABLES}")

    async with async_engine.begin() as conn:
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar() or 0
