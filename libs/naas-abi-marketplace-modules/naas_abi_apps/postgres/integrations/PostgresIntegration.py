"""PostgreSQL, async (``psycopg`` 3), on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.postgres.integrations``: same
tool names. ``get_table_schema`` binds the table name as a parameter (the
in-engine version formatted it into the SQL). ``execute_pandas_query`` is not
ported: the agent never used it, and pandas is not a dependency here.
"""

from __future__ import annotations

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
    """connect: opens an async connection (tests pass a fake)."""

    host: str
    port: int | str
    database: str
    user: str
    password: str
    sslmode: str = "require"
    connect: Callable[..., Any] = field(default=_connect, repr=False)


class PostgresIntegration(Integration):
    """Run queries, list tables and describe a table."""

    def __init__(self, configuration: PostgresIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _connection(self) -> Any:
        c = self.configuration
        try:
            return await c.connect(
                host=c.host,
                port=int(c.port),
                dbname=c.database,
                user=c.user,
                password=c.password,
                sslmode=c.sslmode,
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
        """Run ``query``; the rows when ``fetch``, else commit and the affected row count."""
        connection = await self._connection()
        try:
            async with connection, connection.cursor() as cursor:
                await cursor.execute(query, params)
                if fetch:
                    return [dict(row) for row in await cursor.fetchall()]
                await connection.commit()
                return cursor.rowcount
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
            description="Whether to fetch results (false: commit and return the row count)",
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
