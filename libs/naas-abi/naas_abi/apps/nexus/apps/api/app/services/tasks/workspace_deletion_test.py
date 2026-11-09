"""Deleting a workspace removes its tasks, as it removes its other rows.

Tasks hold no placement and no IAM object: their resources (``task/<id>``,
``task_iteration/<id>``, ``task_settings``) are names under the workspace's
scope, which ``drop_scope`` removes. Their rows go with the workspace through
the foreign keys of migrations ``0059``-``0062`` (``ON DELETE CASCADE``), checked
here on nexus.db built from every migration, with the foreign keys enforced as
PostgreSQL enforces them, through the workspaces adapter the delete route uses.
"""

from __future__ import annotations

import contextlib
import io

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core import database
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

TASK_TABLES = ("task_activity", "task_comments", "tasks", "task_iterations", "task_settings")


@pytest_asyncio.fixture
async def nexus_db(tmp_path, monkeypatch):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")

    @event.listens_for(engine.sync_engine, "connect")
    def _foreign_keys(connection, _record) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

    monkeypatch.setattr(database, "async_engine", engine)
    monkeypatch.setattr(database, "_is_sqlite", True)
    with contextlib.redirect_stdout(io.StringIO()):
        await database.init_db()
    async with AsyncSession(engine) as session:
        yield session
    await engine.dispose()


async def _seed(db: AsyncSession, workspace: str) -> None:
    """A workspace with an iteration, a task, a comment and its reply, an event
    and its settings."""
    for statement in (
        "INSERT INTO users (id, email, name) VALUES (:ws || '-u', :ws || '@x.io', 'U')",
        "INSERT INTO workspaces (id, name, slug, owner_id) VALUES (:ws, :ws, :ws, :ws || '-u')",
        "INSERT INTO task_iterations (id, workspace_id, start_date) "
        "VALUES (:ws || '-it', :ws, '2026-10-19')",
        "INSERT INTO tasks (id, workspace_id, iteration_id, title) "
        "VALUES (:ws || '-t', :ws, :ws || '-it', 'T')",
        "INSERT INTO task_comments (id, workspace_id, task_id, author_id, body) "
        "VALUES (:ws || '-c', :ws, :ws || '-t', :ws || '-u', 'Question')",
        "INSERT INTO task_comments (id, workspace_id, task_id, body, parent_id) "
        "VALUES (:ws || '-r', :ws, :ws || '-t', 'Answer', :ws || '-c')",
        "INSERT INTO task_activity (id, workspace_id, task_id, field) "
        "VALUES (:ws || '-a', :ws, :ws || '-t', 'created')",
        "INSERT INTO task_settings (workspace_id, data) VALUES (:ws, '{}')",
    ):
        await db.execute(text(statement), {"ws": workspace})
    await db.commit()


async def _counts(db: AsyncSession, workspace: str) -> dict[str, int]:
    return {
        table: (
            await db.execute(
                text(f"SELECT COUNT(*) FROM {table} WHERE workspace_id = :ws"),  # noqa: S608
                {"ws": workspace},
            )
        ).scalar_one()
        for table in TASK_TABLES
    }


@pytest.mark.asyncio
async def test_deleting_a_workspace_deletes_its_tasks_and_no_other(nexus_db) -> None:
    await _seed(nexus_db, "ws-1")
    await _seed(nexus_db, "ws-2")

    # As ``DELETE /api/workspaces/{id}`` does it: the ORM's delete of the row.
    assert await WorkspaceSecondaryAdapterPostgres(db=nexus_db).delete_workspace("ws-1")
    await nexus_db.commit()

    assert await _counts(nexus_db, "ws-1") == dict.fromkeys(TASK_TABLES, 0)
    assert await _counts(nexus_db, "ws-2") == {
        "task_activity": 1,
        "task_comments": 2,
        "tasks": 1,
        "task_iterations": 1,
        "task_settings": 1,
    }
