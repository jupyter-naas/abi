# PostgresAgent

## What it is
A PostgreSQL-focused `IntentAgent` that wires in Postgres integration tools and exposes a small set of tool-backed intents (query, schema, tables) using credentials from the Postgres `ABIModule` configuration.

## Public API
- `class PostgresAgent(IntentAgent)`
  - An `IntentAgent` subclass with preset metadata:
    - `name = "PostgreSQL"`
    - `description = "A PostgreSQL Assistant for managing database operations."`
    - `avatar_url = "https://www.postgresql.org/media/img/about/press/elephant.png"`
    - `system_prompt`: instructions for operating as a Postgres assistant.
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> PostgresAgent`
    - Factory that:
      - Fetches default chat and embedding models from `ABIModule.get_instance().engine.services.model_registry`.
      - Builds Postgres tools via `PostgresIntegrationConfiguration(...)` + `as_tools(...)`.
      - Registers intents (all `IntentType.TOOL`):
        - `postgres_query` — “Execute a SQL query”
        - `postgres_schema` — “Show database schema”
        - `postgres_tables` — “List tables”
      - Applies defaults when not provided:
        - `AgentConfiguration(system_prompt=PostgresAgent.system_prompt)`
        - `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on core agent types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Depends on Postgres marketplace module/integration:
  - `naas_abi_marketplace.applications.postgres.ABIModule`
  - `PostgresIntegrationConfiguration`, `as_tools`
- Requires Postgres credentials from `ABIModule.get_instance().configuration`:
  - `postgres_host`
  - `postgres_port` (cast to `int`)
  - `postgres_dbname`
  - `postgres_user`
  - `postgres_password`
- Requires a initialized model registry:
  - `abi_module.engine.services.model_registry` must not be `None` (asserted)

## Usage
```python
from naas_abi_marketplace.applications.postgres.agents.PostgresAgent import PostgresAgent

agent = PostgresAgent.New()
```

## Caveats
- `New()` asserts `ModelRegistryService` is initialized; otherwise it raises an `AssertionError`.
- Tool setup depends on valid Postgres configuration values; missing/invalid credentials will prevent proper integration tool construction.
