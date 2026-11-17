from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import datetime

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.services import audit
from naas_abi.apps.nexus.apps.api.app.services.audit.adapters.secondary.memory import (
    MemoryAuditLog,
)
from naas_abi.apps.nexus.apps.api.app.services.audit.adapters.secondary.sql import SqlAuditLog
from naas_abi.apps.nexus.apps.api.app.services.audit.port import AuditEvent, AuditLogPort
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

AUDIT_LOGS = """
    CREATE TABLE audit_logs (
        id TEXT PRIMARY KEY, user_id TEXT, action TEXT NOT NULL, resource_type TEXT,
        resource_id TEXT, details TEXT, ip_address TEXT, user_agent TEXT,
        success BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMP NOT NULL
    )
"""

EVENT = AuditEvent(
    id="audit-1",
    action="login",
    created_at=datetime(2026, 11, 17, 12, 0, 0),
    user_id="u1",
    details={"method": "oidc"},
    ip_address="10.0.0.1",
    user_agent="pytest",
    success=False,
)


@pytest_asyncio.fixture
async def engine() -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine("sqlite+aiosqlite://")
    async with engine.begin() as conn:
        await conn.execute(text(AUDIT_LOGS))
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture(params=["sql", "memory"])
async def log(request: pytest.FixtureRequest, engine: AsyncEngine) -> AuditLogPort:
    return SqlAuditLog(engine) if request.param == "sql" else MemoryAuditLog()


@pytest.mark.asyncio
async def test_every_adapter_takes_an_event(log) -> None:
    await log.append(EVENT)


@pytest.mark.asyncio
async def test_the_sql_adapter_writes_the_row_the_migration_declares(engine) -> None:
    await SqlAuditLog(engine).append(EVENT)

    async with engine.begin() as conn:
        row = (await conn.execute(text("SELECT * FROM audit_logs"))).mappings().one()

    assert row["id"] == "audit-1" and row["action"] == "login" and row["user_id"] == "u1"
    assert json.loads(row["details"]) == {"method": "oidc"}
    assert (row["ip_address"], row["user_agent"], bool(row["success"])) == (
        "10.0.0.1",
        "pytest",
        False,
    )


@pytest.mark.asyncio
async def test_log_login_writes_one_event(monkeypatch) -> None:
    memory = MemoryAuditLog()
    monkeypatch.setattr(audit, "_log", memory)

    await audit.log_login("u1", success=True, details={"method": "oidc"})

    [event] = memory.events
    assert (event.action, event.user_id, event.success, event.details) == (
        "login",
        "u1",
        True,
        {"method": "oidc"},
    )


@pytest.mark.asyncio
async def test_a_failed_write_never_fails_the_caller(monkeypatch) -> None:
    class Broken(AuditLogPort):
        async def append(self, event: AuditEvent) -> None:
            raise RuntimeError("database down")

    monkeypatch.setattr(audit, "_log", Broken())

    await audit.log_logout("u1")
