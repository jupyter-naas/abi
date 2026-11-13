# PostgresIntegration

## What it is
- A PostgreSQL integration client built on `psycopg2` that:
  - Executes SQL queries (optionally with parameters)
  - Returns results as Python `dict` rows or a pandas `DataFrame`
  - Lists tables and fetches table schema via `information_schema`
- Includes `as_tools()` to expose the integration as LangChain `StructuredTool` tools.

## Public API

### `PostgresIntegrationConfiguration`
Dataclass configuration for connecting to PostgreSQL (extends `IntegrationConfiguration`).
- Fields:
  - `host: str`
  - `port: int`
  - `database: str` (passed to psycopg2 as `dbname`)
  - `user: str`
  - `password: str`
  - `sslmode: str = "require"` (e.g., `disable`, `require`, `verify-ca`, `verify-full`)
  - `read_only: bool = True`: each `execute_query` runs one statement (`single_statement`) in a read-only transaction and is rolled back, never committed. The boundary is still the database role: give the integration a role of its own that may only read.

### `single_statement(query: str) -> bool`
Whether `query` holds one SQL statement: no `;` outside string literals (including `E'...'` and dollar quotes; a `$` inside an identifier opens none), quoted identifiers and comments (a `--` comment ends at `\n` or `\r`), but an optional final one.

### `PostgresIntegration`
Integration client (extends `Integration`).

- `execute_pandas_query(query: str) -> pd.DataFrame`
  - Executes a SQL query and returns results as a pandas DataFrame via `pd.read_sql_query`.

- `execute_query(query: str, params: tuple | dict | None = None, fetch: bool = True) -> list[dict] | int`
  - Executes a SQL statement using a `RealDictCursor`.
  - If `fetch=True`, returns `list[dict]` rows.
  - If `fetch=False`, returns `cur.rowcount`, after a commit when `read_only` is false.
  - With `read_only` (the default): refuses (`ReadOnlyQueryRefused`, a `ValueError`) a query that is not one statement, or that is a transaction or session command (`BEGIN`, `COMMIT`, `ROLLBACK`, `SET`, `RESET`, ...: `read_only_statement`). The check runs on the template and again on the text with its parameters bound (`cursor.mogrify`), and exactly that text is sent. It connects with `default_transaction_read_only=on`, opens the transaction read-only (`set_session(readonly=True)`, `standard_conforming_strings` on), and rolls back.

- `list_tables() -> list[str]`
  - Returns table names in the `public` schema from `information_schema.tables`.

- `get_table_schema(table_name: str) -> list[dict[str, Any]]`
  - Returns column info (`column_name`, `data_type`, `is_nullable`) from `information_schema.columns` for the given table.

### `as_tools(configuration: PostgresIntegrationConfiguration) -> list`
Creates LangChain `StructuredTool` tools backed by a `PostgresIntegration` instance:
- `postgres_execute_query` → calls `PostgresIntegration.execute_query`
- `postgres_list_tables` → calls `PostgresIntegration.list_tables`
- `postgres_get_table_schema` → calls `PostgresIntegration.get_table_schema`

## Configuration/Dependencies
- Runtime dependencies:
  - `psycopg2`
  - `pandas`
  - `naas_abi_core` (`Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- For `as_tools()`:
  - `langchain_core.tools.StructuredTool`
  - `pydantic` (`BaseModel`, `Field`)
- Errors:
  - Connection/query failures are wrapped and raised as `IntegrationConnectionError` with a prefixed message.

## Usage

### Basic usage
```python
from naas_abi_marketplace.applications.postgres.integrations.PostgresIntegration import (
    PostgresIntegration,
    PostgresIntegrationConfiguration,
)

cfg = PostgresIntegrationConfiguration(
    host="localhost",
    port=5432,
    database="postgres",
    user="postgres",
    password="postgres",
    sslmode="require",
)

pg = PostgresIntegration(cfg)

print(pg.list_tables())
print(pg.execute_query("SELECT 1 AS value", fetch=True))
print(pg.execute_pandas_query("SELECT 1 AS value"))
```

### LangChain tools
```python
from naas_abi_marketplace.applications.postgres.integrations.PostgresIntegration import (
    as_tools,
    PostgresIntegrationConfiguration,
)

cfg = PostgresIntegrationConfiguration(
    host="localhost", port=5432, database="postgres", user="postgres", password="postgres"
)

tools = as_tools(cfg)  # list of StructuredTool
```

## Caveats
- `get_table_schema(table_name)` passes `table_name` as a query parameter.
- `execute_query` commits only when `read_only` is false.
- The module's documented configuration names secrets of its own (`POSTGRES_INTEGRATION_*`), never the platform database's.
