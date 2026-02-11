"""
NEXUS Database Module

PostgreSQL-only async database with SQLAlchemy 2.0 ORM.
Uses asyncpg for production-grade performance.
"""

from typing import AsyncGenerator

from sqlalchemy import text, event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

# Known tables for safe row count queries
KNOWN_TABLES = frozenset({
    "users", "organizations", "organization_members",
    "workspaces", "workspace_members", "conversations", "messages",
    "ontologies", "graph_nodes", "graph_edges", "api_keys", "provider_configs",
    "agent_configs", "secrets", "refresh_tokens", "revoked_tokens", 
    "audit_logs", "rate_limit_events", "password_changes", "workspace_secrets",
})


# ============ ORM Base ============

class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


# ============ Async Engine & Session ============

async_engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,        # Connection pool size
    max_overflow=20,     # Max connections above pool_size
)

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
    from pathlib import Path
    import asyncio
    
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
                print("\n💡 Quick fix: Run 'make db-up' to start PostgreSQL")
                raise ConnectionError("Database not available. Run 'make db-up' to start PostgreSQL.") from e
    
    migrations_dir = Path(__file__).parent.parent.parent / "migrations"
    
    # Run migrations in order
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    if not migration_files:
        print("⚠ No migration files found")
        return
    
    print(f"Running migrations...")
    print(f"Found {len(migration_files)} migration(s)")
    
    # Run each migration file in its own transaction
    for migration_file in migration_files:
        print(f"  • {migration_file.name}...", end=" ")
        sql = migration_file.read_text()
        
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
                line = line[:line.index("--")].strip()
            if line:
                current_statement.append(line)
                if line.endswith(";"):
                    statements.append(" ".join(current_statement))
                    current_statement = []
        
        # Execute each statement in its own transaction for idempotency
        executed = 0
        skipped = 0
        for statement in statements:
            statement = statement.strip().rstrip(";")
            if statement:
                try:
                    async with async_engine.begin() as conn:
                        await conn.execute(text(statement))
                        executed += 1
                except Exception as e:
                    error_msg = str(e).lower()
                    # Check if it's an "already exists" error (idempotent)
                    if "already exists" in error_msg or "duplicate" in error_msg:
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
            print(f"⊘ (already applied)")
        else:
            print("⊘ (empty)")
    
    print("✓ Migrations complete")


async def table_exists(table_name: str) -> bool:
    """Check if a table exists in the database."""
    async with async_engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'public' 
                    AND table_name = :name
                )
            """),
            {"name": table_name}
        )
        return result.scalar()


async def get_row_count(table_name: str) -> int:
    """Get the number of rows in a table."""
    if table_name not in KNOWN_TABLES:
        raise ValueError(f"Unknown table: {table_name}. Allowed: {KNOWN_TABLES}")
    
    async with async_engine.begin() as conn:
        result = await conn.execute(text(f"SELECT COUNT(*) FROM {table_name}"))
        return result.scalar() or 0
