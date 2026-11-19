"""The workspaces' drive flags are dropped at start (``0073_drop_drive_flags.sql``),
idempotently, on PostgreSQL and on SQLite."""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.core.database import (
    _DROP_COLUMN_RE,
    _adapt_statement_for_dialect,
)

MIGRATION = Path(__file__).parents[2] / "migrations" / "0073_drop_drive_flags.sql"
FLAGS = ("platform_drive_enabled", "system_drive_enabled")


def _statements() -> list[str]:
    body = "\n".join(
        line for line in MIGRATION.read_text().splitlines() if not line.strip().startswith("--")
    )
    return [s.strip() for s in body.split(";") if s.strip()]


def test_the_migration_drops_both_flags_if_they_exist() -> None:
    assert _statements() == [
        f"ALTER TABLE workspaces DROP COLUMN IF EXISTS {flag}" for flag in FLAGS
    ]


def test_postgresql_runs_it_as_written() -> None:
    for statement in _statements():
        assert _adapt_statement_for_dialect(statement, "postgresql") == [statement]


def test_sqlite_has_no_if_exists_on_drop_column() -> None:
    assert _adapt_statement_for_dialect(
        "ALTER TABLE workspaces DROP COLUMN IF EXISTS platform_drive_enabled", "sqlite"
    ) == ["ALTER TABLE workspaces DROP COLUMN platform_drive_enabled"]


def _run_as_the_runner(conn: sqlite3.Connection) -> int:
    """The runner's SQLite path: adapted statements; a column already dropped skipped."""
    skipped = 0
    for raw in _statements():
        for statement in _adapt_statement_for_dialect(raw, "sqlite"):
            try:
                conn.execute(statement)
            except sqlite3.OperationalError as exc:
                if _DROP_COLUMN_RE.match(statement) and "no such column" in str(exc).lower():
                    skipped += 1
                    continue
                raise
    return skipped


@pytest.mark.skipif(
    tuple(int(p) for p in re.findall(r"\d+", sqlite3.sqlite_version)[:2]) < (3, 35),
    reason="SQLite drops columns from 3.35",
)
def test_sqlite_drops_the_columns_once_then_skips() -> None:
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE workspaces (id TEXT PRIMARY KEY, name TEXT,"
        " platform_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE,"
        " system_drive_enabled BOOLEAN NOT NULL DEFAULT FALSE)"
    )
    conn.execute("INSERT INTO workspaces (id, name) VALUES ('ws-1', 'One')")

    assert _run_as_the_runner(conn) == 0
    columns = {row[1] for row in conn.execute("PRAGMA table_info(workspaces)")}
    assert columns == {"id", "name"}
    assert conn.execute("SELECT name FROM workspaces").fetchall() == [("One",)]
    # Every start runs it again: nothing left to drop.
    assert _run_as_the_runner(conn) == 2
