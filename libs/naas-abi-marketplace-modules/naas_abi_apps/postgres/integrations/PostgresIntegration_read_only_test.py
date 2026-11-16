"""Read-only queries are one statement that leaves the transaction and the
session alone, on a read-only session, and are never committed."""

from __future__ import annotations

import asyncio
import re
from pathlib import Path

import naas_abi_apps.postgres as postgres_pkg
import pytest
from naas_abi_apps.postgres.integrations.PostgresIntegration import (
    ReadOnlyQueryRefused,
    single_statement,
)
from naas_abi_apps.postgres.integrations.PostgresIntegration_test import (
    integration_with,
)

IDENTIFIER_DOLLARS = (
    "SET application_name = a$$a$; SET TRANSACTION READ WRITE; "
    "DELETE FROM t; COMMIT; SELECT 1 AS b$a$"
)


def test_postgres_queries_keep_read_only_by_default() -> None:
    integration, opened = integration_with([{"id": 1}])

    assert asyncio.run(integration.execute_query("SELECT 1")) == [{"id": 1}]

    kwargs, connection = opened[0]
    assert kwargs["options"] == "-c default_transaction_read_only=on"
    assert connection.read_only and connection.prepared == [True]
    assert connection.rolled_back and not connection.committed


@pytest.mark.parametrize(
    "query",
    [
        "SELECT 1; DELETE FROM t",
        "SELECT 1 --\r; COMMIT; BEGIN READ WRITE; DELETE FROM t; COMMIT; SELECT 1",
        IDENTIFIER_DOLLARS,
        "COMMIT",
        "/* x */ commit",
        "BEGIN READ WRITE",
        "START TRANSACTION READ WRITE",
        "SET TRANSACTION READ WRITE",
        "SET SESSION CHARACTERISTICS AS TRANSACTION READ WRITE",
        "set default_transaction_read_only = off",
        "RESET default_transaction_read_only",
        "ROLLBACK",
        "END",
        "ABORT",
        "DO $$ BEGIN DELETE FROM t; END $$",
        "-- note\r\nCOMMIT",
    ],
)
def test_postgres_read_only_queries_keep_the_transaction_alone(query: str) -> None:
    integration, opened = integration_with([])

    with pytest.raises(ReadOnlyQueryRefused):
        asyncio.run(integration.execute_query(query))

    assert opened == []


def test_postgres_read_only_parameters_stay_apart_from_the_sql() -> None:
    integration, opened = integration_with([])
    value = "x\n; COMMIT; BEGIN READ WRITE; DELETE FROM t; COMMIT; --"

    asyncio.run(integration.execute_query("SELECT 1 WHERE a = %s", [value]))

    connection = opened[0][1]
    # Sent as a prepared statement: the value is a parameter, never SQL text.
    assert connection.executed == [("SELECT 1 WHERE a = %s", [value])]
    assert connection.prepared == [True] and not connection.committed


def test_postgres_writes_when_configured() -> None:
    integration, opened = integration_with([], read_only=False)

    asyncio.run(integration.execute_query("BEGIN; DELETE FROM t", fetch=False))

    kwargs, connection = opened[0]
    assert "options" not in kwargs
    assert connection.committed and not connection.read_only


@pytest.mark.parametrize(
    ("query", "single"),
    [
        ("SELECT 1", True),
        ("SELECT 1;  ", True),
        ("SELECT ';' AS s, \"a;b\" FROM t -- ;\n", True),
        ("SELECT 'it''s; fine'", True),
        ("SELECT $$;$$, $tag$ ; $tag$", True),
        ("SELECT 1 /* ; /* ; */ ; */", True),
        ("SELECT 1; SELECT 2", False),
        ("SELECT E'\\''; DROP TABLE t; --'", False),
        ("SELECT $1$; DROP TABLE t; --$1$", False),
        (IDENTIFIER_DOLLARS, False),
        ("SELECT a$b$c FROM t; DROP TABLE t", False),
        ("SELECT price$ FROM t", True),
        ("SELECT 'unterminated", False),
    ],
)
def test_single_statement(query: str, single: bool) -> None:
    assert single_statement(query) is single


def test_postgres_module_keeps_its_own_secret_names() -> None:
    configuration = postgres_pkg.ABIModule.Configuration()
    named = set(configuration.secret_names().values())
    platform = {
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
        "POSTGRES_DB",
    }
    assert named and not named & platform
    # The repository's own configurations, when the package runs from it.
    root = next(
        (
            d
            for d in Path(postgres_pkg.__file__).resolve().parents
            if (d / "config.yaml").is_file()
        ),
        None,
    )
    for config in root.glob("config*.yaml") if root else []:
        used = set(re.findall(r"secret\.([A-Z_]+)", config.read_text()))
        assert not named & used, config
