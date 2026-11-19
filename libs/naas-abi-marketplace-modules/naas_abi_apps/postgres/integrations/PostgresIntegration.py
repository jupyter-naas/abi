"""PostgreSQL, async (``psycopg`` 3), on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.postgres.integrations``: same
tool names. ``get_table_schema`` binds the table name as a parameter (the
in-engine version formatted it into the SQL). ``execute_pandas_query`` is not
ported: the agent never used it, and pandas is not a dependency here.

Read-only by default (``read_only``): the SQL comes from a model, which a
prompt can steer. Each call then runs one statement that leaves the
transaction and the session alone (no BEGIN, COMMIT, SET, RESET, ...: checked
before connecting, ``read_only_statement``), as a prepared statement (which
cannot hold two, and whose parameters are sent apart from the SQL), on a
session whose transactions are read-only by default, in a read-only
transaction that is rolled back, never committed; ``fetch=False`` is refused.
Give the module a database role with only the rights it needs as well:
read-only here is a guard, not a permission system.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)


async def _connect(**kwargs: Any) -> Any:
    import psycopg
    from psycopg.rows import dict_row

    return await psycopg.AsyncConnection.connect(row_factory=dict_row, **kwargs)


@dataclass
class PostgresIntegrationConfiguration(IntegrationConfiguration):
    """connect: opens an async connection (tests pass a fake). read_only:
    one statement per call, in a read-only transaction (see the module doc)."""

    host: str
    port: int | str
    database: str
    user: str
    password: str
    sslmode: str = "require"
    read_only: bool = True
    connect: Callable[..., Any] = field(default=_connect, repr=False)


# A dollar-quote opener: $$ or $tag$ (tags follow identifier rules).
_DOLLAR_TAG = re.compile(r"\$(?:[A-Za-z_][A-Za-z0-9_]*)?\$")

# Statements that end, open or reshape a transaction or the session: never run
# in read-only mode.
_SESSION_KEYWORDS = frozenset(
    {
        "ABORT",
        "BEGIN",
        "CALL",
        "COMMIT",
        "DISCARD",
        "DO",
        "END",
        "PREPARE",
        "RELEASE",
        "RESET",
        "ROLLBACK",
        "SAVEPOINT",
        "SET",
        "START",
    }
)
_WORD = re.compile(r"[A-Za-z_]+")


class ReadOnlyQueryRefused(ValueError):
    """A read-only query that is not one plain statement."""


def _comment_end(text: str, i: int) -> int:
    """Where the ``--`` comment at ``i`` ends: after the line break (``\n`` or
    ``\r``, as PostgreSQL's lexer reads it), else at the end of ``text``."""
    ends = [e for e in (text.find("\n", i), text.find("\r", i)) if e >= 0]
    return min(ends) + 1 if ends else len(text)


def leading_keyword(query: str) -> str:
    """The first word of ``query``, upper-cased, past spaces, comments and
    opening parentheses; "" when there is none."""
    text, i, n = query, 0, len(query)
    while i < n:
        if text[i].isspace() or text[i] == "(":
            i += 1
        elif text.startswith("--", i):
            i = _comment_end(text, i)
        elif text.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if text.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif text.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
        else:
            word = _WORD.match(text, i)
            return word.group(0).upper() if word else ""
    return ""


def read_only_statement(query: str) -> bool:
    """Whether ``query`` is one statement that leaves the transaction and the
    session alone (no COMMIT, BEGIN, SET, ...)."""
    return single_statement(query) and leading_keyword(query) not in _SESSION_KEYWORDS


def single_statement(query: str) -> bool:
    """Whether ``query`` holds one SQL statement: no ``;`` outside string
    literals, quoted identifiers and comments, but an optional final one."""
    text = query
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        if ch == "-" and text.startswith("--", i):
            i = _comment_end(text, i)
        elif ch == "/" and text.startswith("/*", i):
            depth, i = 1, i + 2
            while i < n and depth:
                if text.startswith("/*", i):
                    depth, i = depth + 1, i + 2
                elif text.startswith("*/", i):
                    depth, i = depth - 1, i + 2
                else:
                    i += 1
            if depth:
                return False
        elif ch == "'":
            # E'...' strings take backslash escapes; others double the quote.
            escapes = (
                i > 0
                and text[i - 1] in "eE"
                and (i == 1 or not (text[i - 2].isalnum() or text[i - 2] in "_$"))
            )
            i += 1
            while i < n:
                if escapes and text[i] == "\\":
                    i += 2
                elif text[i] == "'":
                    if text.startswith("''", i):
                        i += 2
                    else:
                        break
                else:
                    i += 1
            if i >= n:
                return False
            i += 1
        elif ch == '"':
            end = text.find('"', i + 1)
            while end >= 0 and text.startswith('""', end):
                end = text.find('"', end + 2)
            if end < 0:
                return False
            i = end + 1
        elif ch == "$":
            # A $ inside an identifier (a$b, a$$b) opens no quote.
            opener = _DOLLAR_TAG.match(text, i)
            if opener and not (
                i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_$")
            ):
                end = text.find(opener.group(0), opener.end())
                if end < 0:
                    return False
                i = end + len(opener.group(0))
            else:
                i += 1
        elif ch == ";":
            return text[i + 1 :].strip() == ""
        else:
            i += 1
    return True


class PostgresIntegration(Integration):
    """Run queries, list tables and describe a table."""

    def __init__(self, configuration: PostgresIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _connection(self) -> Any:
        c = self.configuration
        options: dict[str, str] = {}
        if c.read_only:
            # Every transaction of the session is read-only by default too,
            # not only the one execute_query opens.
            options["options"] = "-c default_transaction_read_only=on"
        try:
            return await c.connect(
                host=c.host,
                port=int(c.port),
                dbname=c.database,
                user=c.user,
                password=c.password,
                sslmode=c.sslmode,
                **options,
            )
        except Exception as exc:
            raise IntegrationConnectionError(
                f"PostgreSQL connection failed: {exc!s}"
            ) from exc

    async def execute_query(
        self,
        query: str,
        params: list[Any] | tuple[Any, ...] | dict[str, Any] | None = None,
        fetch: bool = True,
    ) -> list[dict[str, Any]] | int:
        """Run ``query``; the rows when ``fetch``, else commit and the affected
        row count. Read-only (the default): one statement that leaves the
        transaction and the session alone, read-only, fetched, rolled back."""
        read_only = self.configuration.read_only
        if read_only and not fetch:
            raise IntegrationConnectionError(
                "PostgreSQL is read-only for this module: set its read_only "
                "configuration to false to allow writes"
            )
        if read_only and not read_only_statement(query):
            raise ReadOnlyQueryRefused(
                "Read-only queries run one SQL statement at a time, and no "
                "transaction or session command"
            )
        connection = await self._connection()
        try:
            async with connection:
                if read_only:
                    # Before the first statement: psycopg then opens each
                    # transaction with BEGIN READ ONLY.
                    await connection.set_read_only(True)
                async with connection.cursor() as cursor:
                    await cursor.execute(
                        query, params, prepare=True if read_only else None
                    )
                    if fetch:
                        rows = [dict(row) for row in await cursor.fetchall()]
                    else:
                        rows = None
                if read_only:
                    await connection.rollback()
                    return rows if rows is not None else []
                await connection.commit()
                return rows if rows is not None else cursor.rowcount
        except IntegrationConnectionError:
            raise
        except Exception as exc:
            raise IntegrationConnectionError(
                f"PostgreSQL operation failed: {exc!s}"
            ) from exc

    async def list_tables(self) -> list[str]:
        """Tables of the ``public`` schema."""
        rows = await self.execute_query(
            "SELECT table_name FROM information_schema.tables "
            "WHERE table_schema = 'public' ORDER BY table_name"
        )
        return [row["table_name"] for row in rows] if isinstance(rows, list) else []

    async def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Columns of a table: name, data type, nullable."""
        rows = await self.execute_query(
            "SELECT column_name, data_type, is_nullable FROM information_schema.columns "
            "WHERE table_name = %s ORDER BY ordinal_position",
            (table_name,),
        )
        return rows if isinstance(rows, list) else []


def as_tools(configuration: PostgresIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = PostgresIntegration(configuration)

    class QuerySchema(BaseModel):
        query: str = Field(
            ..., description="SQL query, with %s or %(name)s placeholders for params"
        )
        params: list[Any] | dict[str, Any] | None = Field(
            None, description="Query parameters to be used in the query if needed."
        )
        fetch: bool = Field(
            True,
            description="Whether to fetch results (false: commit and return the "
            "row count; refused when the module is read-only, the default)",
        )

    class ListTablesSchema(BaseModel):
        pass

    class GetTableSchemaSchema(BaseModel):
        table_name: str = Field(..., description="Table name")

    async def execute_query(
        query: str, params: list[Any] | dict[str, Any] | None = None, fetch: bool = True
    ) -> Any:
        return await integration.execute_query(query, params, fetch)

    async def list_tables() -> Any:
        return await integration.list_tables()

    async def get_table_schema(table_name: str) -> Any:
        return await integration.get_table_schema(table_name)

    return [
        StructuredTool(
            name="postgres_execute_query",
            description="Execute a PostgreSQL query",
            coroutine=execute_query,
            args_schema=QuerySchema,
        ),
        StructuredTool(
            name="postgres_list_tables",
            description="Get list of all tables in the connected database",
            coroutine=list_tables,
            args_schema=ListTablesSchema,
        ),
        StructuredTool(
            name="postgres_get_table_schema",
            description="Get schema information for a specific table",
            coroutine=get_table_schema,
            args_schema=GetTableSchemaSchema,
        ),
    ]
