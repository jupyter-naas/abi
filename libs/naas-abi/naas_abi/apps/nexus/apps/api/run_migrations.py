#!/usr/bin/env python3
"""
Run pending database migrations.
"""

import asyncio
from pathlib import Path

from sqlalchemy import text

from app.core.database import _adapt_statement_for_dialect, _is_sqlite, async_engine


async def run_migrations():
    """Run all SQL migrations in order."""
    migrations_dir = Path(__file__).parent / "migrations"

    # Get all migration files
    migration_files = sorted(migrations_dir.glob("*.sql"))

    print(f"Found {len(migration_files)} migration files")

    current_dialect = "sqlite" if _is_sqlite else "postgresql"

    async with async_engine.begin() as conn:
        for migration_file in migration_files:
            print(f"Running: {migration_file.name}")
            sql = migration_file.read_text()

            # Honor `-- @dialect: <name>[, <name>...]` directive.
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
                print(f"  ⊘ Skipped on {current_dialect}")
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
                    line = line[:line.index("--")].strip()
                if line:
                    current_statement.append(line)
                    if line.endswith(";"):
                        statements.append(" ".join(current_statement))
                        current_statement = []

            # Execute each statement
            for raw_statement in statements:
                adapted = _adapt_statement_for_dialect(
                    raw_statement.strip().rstrip(";"), current_dialect
                )
                for statement in adapted:
                    if not statement:
                        continue
                    try:
                        await conn.execute(text(statement))
                        print("  ✓ Executed statement")
                    except Exception as e:
                        error_msg = str(e).lower()
                        if (
                            "already exists" in error_msg
                            or "duplicate column" in error_msg
                        ):
                            print("  ⊘ Already exists (skipping)")
                        else:
                            print(f"  ✗ Error: {e}")
                            # Continue with other migrations

    print("✓ All migrations completed")


if __name__ == "__main__":
    asyncio.run(run_migrations())
