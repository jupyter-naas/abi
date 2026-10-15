"""SQLite ``IAMStore``: the default, ``storage/iam/iam.sqlite`` (``abi dev``).

WAL, a busy timeout, and ``BEGIN IMMEDIATE`` for writes, so concurrent writers
queue instead of failing to upgrade a read lock. ``:memory:`` keeps one
connection, for tests.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from naas_abi_core.services.iam.adapters.secondary.iam_sql import IAMStoreSQL
from sqlalchemy import create_engine, event
from sqlalchemy.pool import StaticPool


class IAMStoreSQLite(IAMStoreSQL):
    _write_options = {"iam_sqlite_immediate": True}

    def __init__(self, path: str = "storage/iam/iam.sqlite", timeout: float = 5.0):
        if path == ":memory:":
            engine = create_engine(
                "sqlite://",
                poolclass=StaticPool,
                connect_args={"check_same_thread": False, "timeout": timeout},
            )
        else:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            engine = create_engine(
                f"sqlite:///{path}",
                connect_args={"check_same_thread": False, "timeout": timeout},
            )
        busy_ms = int(timeout * 1000)

        @event.listens_for(engine, "connect")
        def _connect(dbapi_connection: Any, _record: Any) -> None:
            # SQLAlchemy emits BEGIN itself (below), not the driver.
            dbapi_connection.isolation_level = None
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={busy_ms}")
            if path != ":memory:":
                cursor.execute("PRAGMA journal_mode=WAL")
            cursor.close()

        @event.listens_for(engine, "begin")
        def _begin(connection: Any) -> None:
            immediate = connection.get_execution_options().get("iam_sqlite_immediate")
            connection.exec_driver_sql("BEGIN IMMEDIATE" if immediate else "BEGIN")

        super().__init__(engine)
