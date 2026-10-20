# PostgresAgent

## What it is
A thin wrapper around `IntentAgent` that builds a PostgreSQL-focused assistant with Postgres integration tools and a small set of predefined tool-backed intents (query, schema, tables).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Factory that:
    - Loads the chat model (`gpt_4_1_mini` model import).
    - Applies a default `AgentConfiguration` using `SYSTEM_PROMPT` if none is provided.
    - Applies a default `AgentSharedState(thread_id="0")` if none is provided.
    - Builds Postgres integration tools via `PostgresIntegrationConfiguration` + `as_tools(...)`.
    - Registers tool intents:
      - `postgres_query` (“Execute a SQL query”)
      - `postgres_schema` (“Show database schema”)
      - `postgres_tables` (“List tables”)
    - Returns an instance of `PostgresAgent`.

- `class PostgresAgent(IntentAgent)`
  - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Depends on Naas ABI core agent framework:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Depends on marketplace Postgres application/integration:
  - `naas_abi_marketplace.applications.postgres.ABIModule`
  - `PostgresIntegrationConfiguration`, `as_tools`
- Uses Postgres configuration from `ABIModule.get_instance().configuration`:
  - `postgres_host`
  - `postgres_port` (cast to `int`)
  - `postgres_dbname`
  - `postgres_user`
  - `postgres_password`

## Usage
```python
from naas_abi_marketplace.applications.postgres.agents.PostgresAgent import create_agent

agent = create_agent()
# agent is an IntentAgent configured with postgres tools and intents
```

## Caveats
- The agent always attempts to create Postgres integration tools using `ABIModule` configuration; missing/invalid Postgres settings will likely prevent successful tool setup.
- The `PostgresAgent` class itself adds no methods; behavior is inherited from `IntentAgent`.
