"""Offline tests of the PostgreSQL integration: a fake async connection."""

from __future__ import annotations

import asyncio
from typing import Any, Self

import pytest
from naas_abi_apps.postgres.integrations.PostgresIntegration import (
    PostgresIntegration,
    PostgresIntegrationConfiguration,
    as_tools,
)
from naas_abi_sdk.integration import IntegrationConnectionError


class FakeCursor:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection
        self.rowcount = 0

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        return None

    async def execute(self, query: str, params: Any = None) -> None:
        if "boom" in query:
            raise RuntimeError("syntax error")
        self.connection.executed.append((query, params))
        self.rowcount = 3

    async def fetchall(self) -> list[dict[str, Any]]:
        return self.connection.rows


class FakeConnection:
    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self.rows = rows
        self.executed: list[tuple[str, Any]] = []
        self.committed = False
        self.closed = False

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(self, *exc: object) -> None:
        self.closed = True

    def cursor(self) -> FakeCursor:
        return FakeCursor(self)

    async def commit(self) -> None:
        self.committed = True


def integration_with(rows: list[dict[str, Any]]) -> tuple[PostgresIntegration, list]:
    opened: list[tuple[dict[str, Any], FakeConnection]] = []

    async def connect(**kwargs: Any) -> FakeConnection:
        connection = FakeConnection(rows)
        opened.append((kwargs, connection))
        return connection

    configuration = PostgresIntegrationConfiguration(
        host="db", port="5433", database="d", user="u", password="p", connect=connect
    )
    return PostgresIntegration(configuration), opened


def test_fetch_returns_rows_and_closes_the_connection() -> None:
    integration, opened = integration_with([{"id": 1}])

    assert asyncio.run(integration.execute_query("SELECT 1")) == [{"id": 1}]
    kwargs, connection = opened[0]
    assert (
        kwargs["port"] == 5433
        and kwargs["dbname"] == "d"
        and kwargs["sslmode"] == "require"
    )
    assert connection.closed and not connection.committed


def test_writes_commit_and_return_the_row_count() -> None:
    integration, opened = integration_with([])

    assert (
        asyncio.run(integration.execute_query("UPDATE t SET a = %s", [1], fetch=False))
        == 3
    )
    assert opened[0][1].committed


def test_table_schema_binds_the_name() -> None:
    integration, opened = integration_with([{"column_name": "id"}])

    asyncio.run(integration.get_table_schema("users'; DROP TABLE users; --"))

    query, params = opened[0][1].executed[0]
    assert "DROP" not in query
    assert params == ("users'; DROP TABLE users; --",)


def test_errors_and_tools() -> None:
    integration, _ = integration_with([{"table_name": "a"}])

    with pytest.raises(IntegrationConnectionError, match="syntax error"):
        asyncio.run(integration.execute_query("boom"))
    tools = {t.name: t for t in as_tools(integration.configuration)}
    assert set(tools) == {
        "postgres_execute_query",
        "postgres_list_tables",
        "postgres_get_table_schema",
    }
    assert asyncio.run(tools["postgres_list_tables"].ainvoke({})) == ["a"]
    # fetch was required in the in-engine schema; it defaults to true now.
    assert asyncio.run(
        tools["postgres_execute_query"].ainvoke({"query": "SELECT 1"})
    ) == [{"table_name": "a"}]
