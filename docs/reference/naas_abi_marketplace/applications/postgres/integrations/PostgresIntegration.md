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

### `PostgresIntegration`
Integration client (extends `Integration`).

- `execute_pandas_query(query: str) -> pd.DataFrame`
  - Executes a SQL query and returns results as a pandas DataFrame via `pd.read_sql_query`.

- `execute_query(query: str, params: tuple | dict | None = None, fetch: bool = True) -> list[dict] | int`
  - Executes a SQL statement using a `RealDictCursor`.
  - If `fetch=True`, returns `list[dict]` rows.
  - If `fetch=False`, commits and returns `cur.rowcount`.

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
- `get_table_schema(table_name)` interpolates `table_name` directly into the SQL string (no parameterization). Only pass trusted table names.
- `execute_query(..., fetch=False)` commits; `fetch=True` does not explicitly commit (suitable for `SELECT`-style queries).
