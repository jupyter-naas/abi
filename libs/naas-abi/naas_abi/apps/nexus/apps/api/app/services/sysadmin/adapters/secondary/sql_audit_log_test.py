import asyncio
import json
import re
from pathlib import Path

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.adapters.secondary.sql_audit_log import (
    SqlAdminAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.contracts import AdminAuditLogContract
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import (
    AdminAction,
    AuditRecord,
)
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

MIGRATIONS = Path(__file__).parents[5] / "migrations"


def _ddl(table: str, migration: str) -> str:
    text_ = (MIGRATIONS / migration).read_text()
    match = re.search(rf"CREATE TABLE IF NOT EXISTS {table} \(.*?\n\);", text_, re.S)
    assert match, f"{table} DDL not found in {migration}"
    return match.group(0)


def _create_table_sql() -> str:
    return _ddl("audit_logs", "0002_security_enhancements.sql")


@pytest.fixture
def engine(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.db'}")

    async def create():
        async with engine.begin() as conn:
            await conn.execute(text(_ddl("users", "0001_initial.sql")))
            await conn.execute(text(_create_table_sql()))
            await conn.execute(
                text(
                    "INSERT INTO users (id, email, name, hashed_password) "
                    "VALUES ('u1', 'ada@example.com', 'Ada', 'x')"
                )
            )

    asyncio.run(create())
    yield engine
    asyncio.run(engine.dispose())


class TestSqlAdminAuditLog(AdminAuditLogContract):
    @pytest.fixture
    def audit(self, engine):
        return SqlAdminAuditLog(lambda: engine)

    @pytest.fixture
    def recorded(self, engine):
        async def rows():
            async with engine.connect() as conn:
                result = await conn.execute(
                    text(
                        "SELECT user_id, action, resource_type, resource_id, details "
                        "FROM audit_logs ORDER BY rowid"
                    )
                )
                return result.all()

        def read():
            records = []
            for user_id, action, service, resource_id, details in asyncio.run(rows()):
                info = json.loads(details)
                operation = action.removeprefix("sysadmin.")
                records.append(
                    AuditRecord(
                        AdminAction(user_id, service, operation, resource_id),
                        info["phase"],
                        info.get("error", ""),
                    )
                )
            return records

        return read

    @pytest.fixture
    def broken_audit(self, tmp_path):
        # No audit_logs table: every insert fails.
        empty = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'empty.db'}")
        return SqlAdminAuditLog(lambda: empty)


def test_rows_use_the_shared_audit_vocabulary(engine):
    audit = SqlAdminAuditLog(lambda: engine)
    action = AdminAction("u1", "object_storage", "delete", "docs/a.txt")

    asyncio.run(audit.record(AuditRecord(action, "failed", error="RuntimeError")))

    async def row():
        async with engine.connect() as conn:
            return (
                await conn.execute(text("SELECT action, success, details FROM audit_logs"))
            ).one()

    action_name, success, details = asyncio.run(row())
    assert action_name == "sysadmin.delete"
    assert not success
    assert json.loads(details) == {"phase": "failed", "error": "RuntimeError"}


def test_history_names_the_actor_and_parses_timestamps(engine):
    audit = SqlAdminAuditLog(lambda: engine)
    action = AdminAction("u1", "keyvalue", "delete", "session:42")

    asyncio.run(audit.record(AuditRecord(action, "succeeded")))
    (entry,) = asyncio.run(audit.history(resource_id="session:42"))

    assert (entry.actor_id, entry.actor) == ("u1", "Ada")
    assert entry.at.endswith("+00:00") and "T" in entry.at
