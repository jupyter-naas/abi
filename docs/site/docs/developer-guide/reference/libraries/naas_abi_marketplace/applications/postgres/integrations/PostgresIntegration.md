# PostgresIntegration

## What it is
- A PostgreSQL integration client built on `psycopg2` that:
  - Executes SQL queries (optionally with parameters)
  - Returns results as Python dicts or a pandas `DataFrame`
  - Lists tables and fetches table schema from `information_schema`
- Includes `as_tools()` to expose the integration as LangChain `StructuredTool` tools.

## Public API

### `PostgresIntegrationConfiguration`
Dataclass configuration for connecting to PostgreSQL.
- Fields:
  - `host: str`
  - `port: int`
  - `database: str` (mapped to `dbname` in psycopg2)
  - `user: str`
  - `password: str`
  - `sslmode: str = "require"`

### `PostgresIntegration`
Integration client.

- `execute_pandas_query(query: str) -> pd.DataFrame`
  - Runs a SQL query and returns a pandas `DataFrame` via `pd.read_sql_query`.

- `execute_query(query: str, params: Optional[Union[Tuple, Dict]] = None, fetch: bool = True) -> Union[List[Dict], int]`
  - Executes a SQL statement.
  - If `fetch=True`, returns `List[Dict]` rows (cursor uses `RealDictCursor`).
  - If `fetch=False`, commits and returns `rowcount`.

- `list_tables() -> List[str]`
  - Returns table names in the `public` schema from `information_schema.tables`.

- `get_table_schema(table_name: str) -> List[Dict[str, Any]]`
  - Returns column info (`column_name`, `data_type`, `is_nullable`) from `information_schema.columns` for the given table.

### `as_tools(configuration: PostgresIntegrationConfiguration) -> list`
Converts the integration into LangChain tools (`langchain_core.tools.StructuredTool`):
- `postgres_execute_query` → `PostgresIntegration.execute_query`
- `postgres_list_tables` → `PostgresIntegration.list_tables`
- `postgres_get_table_schema` → `PostgresIntegration.get_table_schema`

## Configuration/Dependencies
- Requires:
  - `psycopg2`
  - `pandas`
  - `naas_abi_core` (`Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- For `as_tools()`:
  - `langchain_core`
  - `pydantic`
- Connection parameters are taken from `PostgresIntegrationConfiguration` and passed to `psycopg2.connect(...)` including `sslmode`.

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

tables = pg.list_tables()
print(tables)

rows = pg.execute_query("SELECT 1 AS value", fetch=True)
print(rows)

affected = pg.execute_query("CREATE TABLE IF NOT EXISTS t(x int)", fetch=False)
print(affected)

df = pg.execute_pandas_query("SELECT 1 AS value")
print(df)
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

tools = as_tools(cfg)
# tools is a list of StructuredTool instances
```

## Caveats
- `get_table_schema(table_name)` interpolates `table_name` directly into SQL (no parameterization), so callers must ensure `table_name` is trusted.
- All failures are wrapped and re-raised as `IntegrationConnectionError` (including query errors), with a prefixed message.
