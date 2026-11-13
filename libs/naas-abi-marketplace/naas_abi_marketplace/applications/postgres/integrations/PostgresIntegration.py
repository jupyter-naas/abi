import re
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

import pandas as pd
import psycopg2
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from psycopg2.extras import RealDictCursor


@dataclass
class PostgresIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for PostgreSQL integration.

    Attributes:
        host (str): Database host
        port (int): Database port
        database (str): Database name
        user (str): Database user
        password (str): Database password
        sslmode (str): SSL mode (disable, require, verify-ca, verify-full)
        read_only (bool): Run each query alone in a read-only transaction and
            never commit (the default). The database role is the boundary: give
            this integration a role of its own that may only read.
    """

    host: str
    port: int
    database: str
    user: str
    password: str
    sslmode: str = "require"
    read_only: bool = True


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
            escapes = i > 0 and text[i - 1] in "eE" and (
                i == 1 or not (text[i - 2].isalnum() or text[i - 2] in "_$")
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
            if opener and not (i > 0 and (text[i - 1].isalnum() or text[i - 1] in "_$")):
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
    """PostgreSQL integration client.

    This integration provides methods to interact with PostgreSQL's API endpoints.
    """

    __configuration: PostgresIntegrationConfiguration

    def __init__(self, configuration: PostgresIntegrationConfiguration):
        """Initialize PostgreSQL client."""
        super().__init__(configuration)
        self.__configuration = configuration

    @contextmanager
    def __get_connection(self):
        """Create a database connection context.

        Yields:
            psycopg2.extensions.connection: Database connection

        Raises:
            IntegrationConnectionError: If connection fails
        """
        options = {}
        if self.__configuration.read_only:
            # Every transaction of the session is read-only by default too,
            # not only the one execute_query opens.
            options["options"] = "-c default_transaction_read_only=on"
        try:
            connection = psycopg2.connect(
                host=self.__configuration.host,
                port=self.__configuration.port,
                dbname=self.__configuration.database,
                user=self.__configuration.user,
                password=self.__configuration.password,
                sslmode=self.__configuration.sslmode,
                **options,
            )
        except Exception as e:  # noqa: BLE001
            raise IntegrationConnectionError(f"PostgreSQL connection failed: {e!s}")
        try:
            yield connection
        finally:
            connection.close()

    def execute_pandas_query(self, query: str) -> pd.DataFrame:
        """Execute a SQL query and return results as a pandas DataFrame.

        Args:
            query (str): SQL query to execute

        Returns:
            pd.DataFrame: Query results as a pandas DataFrame

        Raises:
            IntegrationConnectionError: If the operation fails
        """
        try:
            with self.__get_connection() as conn:
                return pd.read_sql_query(query, conn)
        except Exception as e:  # noqa: BLE001
            raise IntegrationConnectionError(f"PostgreSQL query failed: {e!s}")

    def execute_query(
        self,
        query: str,
        params: tuple | dict | None = None,
        fetch: bool = True,
    ) -> list[dict] | int:
        """Execute a SQL query.

        Args:
            query (str): SQL query
            params (Optional[Union[Tuple, Dict]], optional): Query parameters. Defaults to None.
            fetch (bool, optional): Whether to fetch results. Defaults to True.

        Returns:
            Union[List[Dict], int]: Query results or number of affected rows
        """
        read_only = self.__configuration.read_only
        refused = ReadOnlyQueryRefused(
            "Read-only queries run one SQL statement at a time, and no "
            "transaction or session command"
        )
        if read_only and not read_only_statement(query):
            raise refused
        try:
            with self.__get_connection() as conn:
                if read_only:
                    # Every transaction of this connection starts READ ONLY,
                    # and backslashes in '...' literals are plain characters,
                    # as single_statement reads them.
                    conn.set_session(readonly=True)
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if read_only:
                        cur.execute("SET standard_conforming_strings = on")
                        # The check reads the text the server gets, parameters
                        # bound, and exactly that text is sent.
                        bound = cur.mogrify(query, params)
                        codec = psycopg2.extensions.encodings.get(
                            getattr(conn, "encoding", "UTF8"), "utf-8"
                        )
                        text = bound.decode(codec) if isinstance(bound, bytes) else bound
                        if not read_only_statement(text):
                            raise refused
                        cur.execute(text)
                    else:
                        cur.execute(query, params)
                    if fetch:
                        results = [dict(row) for row in cur.fetchall()]
                    else:
                        results = cur.rowcount
                if read_only:
                    conn.rollback()
                else:
                    conn.commit()
                return results
        except ReadOnlyQueryRefused:
            raise
        except Exception as e:  # noqa: BLE001
            raise IntegrationConnectionError(f"PostgreSQL operation failed: {e!s}")

    def list_tables(self) -> list[str]:
        """Get list of all tables in the connected database.

        Returns:
            List[str]: List of table names
        """
        query = """
            SELECT table_name 
            FROM information_schema.tables
            WHERE table_schema = 'public'
            ORDER BY table_name;
        """
        try:
            results = self.execute_query(query)
            if isinstance(results, list):
                return [row["table_name"] for row in results]
            else:
                return []
        except Exception as e:  # noqa: BLE001
            raise IntegrationConnectionError(f"Failed to list tables: {e!s}")

    def get_table_schema(self, table_name: str) -> list[dict[str, Any]]:
        """Get schema information for a specific table.

        Args:
            table_name (str): Table name

        Returns:
            Dict[str, Any]: Table schema information
        """
        query = """
            SELECT column_name, data_type, is_nullable
            FROM information_schema.columns
            WHERE table_name = %(table_name)s
            ORDER BY ordinal_position;
        """
        try:
            results = self.execute_query(query, {"table_name": table_name})
            if isinstance(results, list):
                return [dict(row) for row in results]
            else:
                return []
        except Exception as e:  # noqa: BLE001
            raise IntegrationConnectionError(f"Failed to get table schema: {e!s}")


def as_tools(configuration: PostgresIntegrationConfiguration):
    """Convert PostgreSQL integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = PostgresIntegration(configuration)

    class QuerySchema(BaseModel):
        query: str = Field(..., description="SQL query")
        params: tuple | dict | None = Field(
            None, description="Query parameters to be used in the query if needed."
        )
        fetch: bool = Field(description="Whether to fetch results")

    class ListTablesSchema(BaseModel):
        pass

    class GetTableSchemaSchema(BaseModel):
        table_name: str = Field(..., description="Table name")

    return [
        StructuredTool(
            name="postgres_execute_query",
            description=(
                "Execute one PostgreSQL statement"
                + (" in a read-only transaction" if configuration.read_only else "")
            ),
            func=lambda query, params, fetch: integration.execute_query(
                query, params, fetch
            ),
            args_schema=QuerySchema,
        ),
        StructuredTool(
            name="postgres_list_tables",
            description="Get list of all tables in the connected database",
            func=lambda: integration.list_tables(),
            args_schema=ListTablesSchema,
        ),
        StructuredTool(
            name="postgres_get_table_schema",
            description="Get schema information for a specific table",
            func=lambda table_name: integration.get_table_schema(table_name),
            args_schema=GetTableSchemaSchema,
        ),
    ]
