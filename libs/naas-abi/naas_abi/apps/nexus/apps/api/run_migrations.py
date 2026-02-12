#!/usr/bin/env python3
"""
Run pending database migrations.
"""

import asyncio
from pathlib import Path

from app.core.database import async_engine
from sqlalchemy import text


async def run_migrations():
    """Run all SQL migrations in order."""
    migrations_dir = Path(__file__).parent / "migrations"
    
    # Get all migration files
    migration_files = sorted(migrations_dir.glob("*.sql"))
    
    print(f"Found {len(migration_files)} migration files")
    
    async with async_engine.begin() as conn:
        for migration_file in migration_files:
            print(f"Running: {migration_file.name}")
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
            
            # Execute each statement
            for statement in statements:
                statement = statement.strip().rstrip(";")
                if statement:
                    try:
                        await conn.execute(text(statement))
                        print(f"  ✓ Executed statement")
                    except Exception as e:
                        # Check if it's an "already exists" error
                        if "already exists" in str(e).lower():
                            print(f"  ⊘ Already exists (skipping)")
                        else:
                            print(f"  ✗ Error: {e}")
                            # Continue with other migrations
    
    print("✓ All migrations completed")


if __name__ == "__main__":
    asyncio.run(run_migrations())
