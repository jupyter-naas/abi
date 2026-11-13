"""The Postgres tool reads by default: one statement, in a read-only
transaction, never committed; and its template names secrets of its own."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import naas_abi_marketplace.applications.postgres as postgres_pkg
import pytest
from naas_abi_marketplace.applications.postgres.integrations import (
    PostgresIntegration as pg_mod,
)
from naas_abi_marketplace.applications.postgres.integrations.PostgresIntegration import (
    PostgresIntegrationConfiguration,
    as_tools,
    single_statement,
)

# A $ inside an identifier, then statements a dollar quote would have hidden.
IDENTIFIER_DOLLARS = (
    "SET application_name = a$$a$; SET TRANSACTION READ WRITE; "
    "DELETE FROM t; COMMIT; SELECT 1 AS b$a$"
)


def _quoted(value: Any) -> str:
    return pg_mod.psycopg2.extensions.adapt(value).getquoted().decode()


class Recorder:
    def __init__(self) -> None:
        self.executed: list[str] = []
        self.readonly: bool | None = None
        self.committed = False
        self.rolled_back = False
        self.connect_options: str | None = None


@pytest.fixture
def db(monkeypatch: pytest.MonkeyPatch) -> Recorder:
    rec = Recorder()

    class Cursor:
        rowcount = 1

        def __enter__(self) -> Any:
            return self

        def __exit__(self, *a: object) -> None:
            return None

        def execute(self, query: str, params: Any = None) -> None:
            rec.executed.append(query)

        def mogrify(self, query: str, params: Any = None) -> bytes:
            # As psycopg2 binds: each value quoted into the text.
            if params is None:
                return query.encode()
            if isinstance(params, dict):
                quoted: Any = {k: _quoted(v) for k, v in params.items()}
            else:
                quoted = tuple(_quoted(v) for v in params)
            return (query % quoted).encode()

        def fetchall(self) -> list:
            return []

    class Connection:
        def set_session(self, readonly: bool | None = None, **kw: Any) -> None:
            rec.readonly = readonly

        def cursor(self, **kw: Any) -> Cursor:
            return Cursor()

        def commit(self) -> None:
            rec.committed = True

        def rollback(self) -> None:
            rec.rolled_back = True

        def close(self) -> None:
            pass

    def connect(**kw: Any) -> Connection:
        rec.connect_options = kw.get("options")
        return Connection()

    monkeypatch.setattr(pg_mod.psycopg2, "connect", connect)
    return rec


def run(query: str, params: Any = None, **configuration: Any) -> Any:
    tools = {
        t.name: t
        for t in as_tools(
            PostgresIntegrationConfiguration(
                host="db",
                port=5432,
                database="d",
                user="u",
                password="p",
                **configuration,
            )
        )
    }
    return tools["postgres_execute_query"].invoke(
        {"query": query, "params": params, "fetch": False}
    )


def test_postgres_queries_keep_read_only_by_default(db: Recorder) -> None:
    run("UPDATE users SET is_admin = true")

    assert db.readonly is True
    assert db.connect_options == "-c default_transaction_read_only=on"
    assert db.executed[-1] == "UPDATE users SET is_admin = true"
    assert not db.committed
    assert db.rolled_back


def test_postgres_read_only_queries_keep_to_one_statement(db: Recorder) -> None:
    for query in (
        "SELECT 1; COMMIT; UPDATE users SET is_admin = true",
        "SELECT E'\\''; COMMIT; UPDATE users SET is_admin = true; --'",
        "SELECT $q$x$q$; COMMIT; UPDATE users SET is_admin = true",
        IDENTIFIER_DOLLARS,
    ):
        with pytest.raises(ValueError):
            run(query)

    assert db.executed == []


def test_postgres_writes_when_configured(db: Recorder) -> None:
    run("UPDATE t SET x = 1", read_only=False)

    assert db.readonly is None
    assert db.connect_options is None
    assert db.committed


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


def test_postgres_template_keeps_its_own_secret_names() -> None:
    doc = postgres_pkg.ABIModule.Configuration.__doc__ or ""
    named = set(re.findall(r"secret\.([A-Z_]+)", doc))
    assert named
    platform = {"POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"}
    assert not named & platform
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


def test_postgres_read_only_queries_keep_line_breaks_as_comment_ends(
    db: Recorder,
) -> None:
    with pytest.raises(ValueError):
        run("SELECT 1 --\r; COMMIT; BEGIN READ WRITE; DELETE FROM t; COMMIT; SELECT 1")

    assert db.executed == []


def test_postgres_read_only_queries_keep_to_one_statement_once_bound(
    db: Recorder,
) -> None:
    with pytest.raises(ValueError):
        run(
            "SELECT 1 -- %s",
            ["x\n; COMMIT; BEGIN READ WRITE; DELETE FROM t; COMMIT; --"],
        )

    assert db.executed == ["SET standard_conforming_strings = on"]
    assert not db.committed


@pytest.mark.parametrize(
    "query",
    [
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
        "-- note\r\nCOMMIT",
    ],
)
def test_postgres_read_only_queries_keep_the_transaction_alone(
    db: Recorder, query: str
) -> None:
    with pytest.raises(ValueError):
        run(query)

    assert db.executed == []


def test_postgres_read_only_queries_send_the_text_they_checked(db: Recorder) -> None:
    run("SELECT * FROM t WHERE a = %s", ["it's"])

    assert db.executed[-1] == "SELECT * FROM t WHERE a = 'it''s'"
