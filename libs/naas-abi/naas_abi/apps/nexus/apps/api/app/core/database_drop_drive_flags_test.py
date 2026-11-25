"""The workspaces' drive flags are dropped at start (``0073_drop_drive_flags.sql``),
idempotently, on PostgreSQL and on SQLite. On PostgreSQL the flagged workspaces are
first kept in ``workspace_drive_flags_legacy`` for the conversion (#1590); SQLite has
no ``DO`` block, so the runner skips the copy there and nothing is kept."""

from __future__ import annotations

import os
import re
import sqlite3
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.database import (
    _adapt_statement_for_dialect,
    run_migration_statements,
    split_statements,
)
from sqlalchemy import inspect, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

MIGRATION = Path(__file__).parents[2] / "migrations" / "0073_drop_drive_flags.sql"
FLAGS = ("platform_drive_enabled", "system_drive_enabled")
HOLDING = "workspace_drive_flags_legacy"
DROPS = [f"ALTER TABLE workspaces DROP COLUMN IF EXISTS {flag};" for flag in FLAGS]

# PostgreSQL, when given: postgresql+asyncpg://user:pass@host:5432/db (each test works in a
# schema of its own, dropped after).
POSTGRES_DSN = os.environ.get("NEXUS_TEST_POSTGRES_DSN")

_SQLITE_DROPS_COLUMNS = tuple(int(p) for p in re.findall(r"\d+", sqlite3.sqlite_version)[:2]) >= (
    3,
    35,
)


def _statements() -> list[str]:
    return split_statements(MIGRATION.read_text())


def test_the_migration_keeps_the_flags_then_drops_both_columns() -> None:
    statements = _statements()
    assert statements[1:] == DROPS
    block = statements[0]
    assert block.startswith("DO $$") and block.endswith("END $$;")
    assert HOLDING in block and "information_schema.columns" in block


def test_a_dollar_quoted_block_is_one_statement_without_its_comment_lines() -> None:
    sql = "\n".join(
        [
            "-- a comment",
            "DO $$",
            "BEGIN",
            "  -- inside the block",
            "  PERFORM 1;",
            "END $$;",
            "SELECT 2; -- trailing",
        ]
    )
    assert split_statements(sql) == ["DO $$ BEGIN PERFORM 1; END $$;", "SELECT 2;"]


def test_postgresql_runs_it_as_written() -> None:
    for statement in _statements():
        assert _adapt_statement_for_dialect(statement, "postgresql") == [statement]


def test_sqlite_skips_the_block_and_has_no_if_exists_on_drop_column() -> None:
    block, *drops = _statements()
    assert _adapt_statement_for_dialect(block, "sqlite") == []
    assert _adapt_statement_for_dialect(drops[0], "sqlite") == [
        "ALTER TABLE workspaces DROP COLUMN platform_drive_enabled;"
    ]


async def _workspaces(engine: AsyncEngine, rows: list[tuple[str, bool, bool]]) -> None:
    async with engine.begin() as conn:
        await conn.execute(text(f"DROP TABLE IF EXISTS {HOLDING}"))
        await conn.execute(text("DROP TABLE IF EXISTS workspaces"))
        await conn.execute(
            text(
                "CREATE TABLE workspaces (id VARCHAR(255) PRIMARY KEY, name VARCHAR(255),"
                " platform_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE,"
                " system_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE)"
            )
        )
        for workspace, platform, system in rows:
            await conn.execute(
                text(
                    "INSERT INTO workspaces (id, name, platform_drive_enabled,"
                    " system_drive_enabled) VALUES (:id, :id, :p, :s)"
                ),
                {"id": workspace, "p": platform, "s": system},
            )


async def _state(engine: AsyncEngine) -> tuple[set[str], list[tuple[str, bool, bool]] | None]:
    """The workspaces' columns, and the holding table's rows (None without one)."""
    async with engine.connect() as conn:
        columns, held = await conn.run_sync(
            lambda sync: (
                {c["name"] for c in inspect(sync).get_columns("workspaces")},
                inspect(sync).has_table(HOLDING),
            )
        )
        if not held:
            return columns, None
        rows = await conn.execute(
            text(
                f"SELECT workspace_id, platform_drive_enabled, system_drive_enabled FROM {HOLDING}"
                " ORDER BY workspace_id"
            )
        )
        return columns, [(str(w), bool(p), bool(s)) for w, p, s in rows.all()]


FLAGGED = [("ws-1", True, False), ("ws-2", False, True), ("ws-3", False, False)]


@pytest.mark.skipif(not _SQLITE_DROPS_COLUMNS, reason="SQLite drops columns from 3.35")
@pytest.mark.asyncio
async def test_sqlite_drops_the_columns_once_then_skips_and_keeps_nothing(tmp_path) -> None:
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}")
    try:
        await _workspaces(engine, FLAGGED)

        assert await run_migration_statements(_statements(), "sqlite", engine) == (2, 0)
        assert await _state(engine) == ({"id", "name"}, None)
        # Every start runs it again: nothing left to drop.
        assert await run_migration_statements(_statements(), "sqlite", engine) == (0, 2)
        async with engine.connect() as conn:
            names = await conn.execute(text("SELECT name FROM workspaces ORDER BY id"))
            assert [row[0] for row in names] == ["ws-1", "ws-2", "ws-3"]
    finally:
        await engine.dispose()


@pytest_asyncio.fixture
async def postgres():
    """An engine whose ``search_path`` is a schema of its own, dropped after."""
    if not POSTGRES_DSN:
        pytest.skip("Set NEXUS_TEST_POSTGRES_DSN to run 0073 on PostgreSQL")
    schema = f"nexus_0073_{uuid.uuid4().hex[:8]}"
    admin = create_async_engine(POSTGRES_DSN)
    async with admin.begin() as conn:
        await conn.execute(text(f"CREATE SCHEMA {schema}"))
    engine = create_async_engine(
        POSTGRES_DSN, connect_args={"server_settings": {"search_path": schema}}
    )
    try:
        yield engine
    finally:
        await engine.dispose()
        async with admin.begin() as conn:
            await conn.execute(text(f"DROP SCHEMA {schema} CASCADE"))
        await admin.dispose()


@pytest.mark.asyncio
async def test_postgresql_keeps_the_flagged_workspaces_then_is_a_noop(postgres) -> None:
    await _workspaces(postgres, FLAGGED)

    assert await run_migration_statements(_statements(), "postgresql", postgres) == (3, 0)
    kept = [("ws-1", True, False), ("ws-2", False, True)]
    assert await _state(postgres) == ({"id", "name"}, kept)

    # The next start: the columns are gone, the copy and the drops do nothing.
    await run_migration_statements(_statements(), "postgresql", postgres)
    assert await _state(postgres) == ({"id", "name"}, kept)

    # Converted (#1590: the holding table dropped): a later start does not bring it back.
    async with postgres.begin() as conn:
        await conn.execute(text(f"DROP TABLE {HOLDING}"))
    await run_migration_statements(_statements(), "postgresql", postgres)
    assert await _state(postgres) == ({"id", "name"}, None)


@pytest.mark.asyncio
async def test_postgresql_without_a_flagged_workspace_keeps_no_table(postgres) -> None:
    await _workspaces(postgres, [("ws-3", False, False)])

    await run_migration_statements(_statements(), "postgresql", postgres)
    assert await _state(postgres) == ({"id", "name"}, None)
