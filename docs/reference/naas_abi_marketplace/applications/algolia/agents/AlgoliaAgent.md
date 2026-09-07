# AlgoliaAgent

## What it is
- An `IntentAgent` specialization for interacting with Algolia search services.
- Provides a `New()` factory that wires:
  - Algolia integration tools (from the marketplace integration layer)
  - Default chat and embedding models from the module’s model registry
  - A system prompt that lists available tools and operational guidelines
  - A set of tool-backed intents (search, add records, list indexes, index stats)

## Public API
- `class AlgoliaAgent(IntentAgent)`
  - Static metadata:
    - `name: str = "Algolia"`
    - `description: str = "..."`
    - `system_prompt: str = ...` (includes tool list placeholder `[TOOLS]`)
    - `suggestions: list[str] = []`
- `AlgoliaAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> AlgoliaAgent`
  - Creates and returns a configured `AlgoliaAgent`.
  - Defaults:
    - `agent_shared_state` → `AgentSharedState(thread_id="0")`
    - `agent_configuration` → `AgentConfiguration(system_prompt=<system_prompt with tools injected>)`
  - Configures:
    - `chat_model` via `registry.get_default_chat_model()`
    - `embedding_model` via `registry.get_default_embedding_model().model`
    - Algolia tools via `as_tools(AlgoliaIntegrationConfiguration(app_id, api_key))`
    - Intents (tool targets):
      - `algolia_search`
      - `algolia_add_record`
      - `algolia_list_indexes`
      - `algolia_index_stats`

## Configuration/Dependencies
- Depends on:
  - `naas_abi_marketplace.applications.algolia.ABIModule.get_instance()`
  - The module’s model registry: `abi_module.engine.services.model_registry` (must be initialized; asserted)
  - Algolia configuration values:
    - `module.configuration.algolia_application_id`
    - `module.configuration.algolia_api_key`
- Uses integration tooling:
  - `AlgoliaIntegrationConfiguration(app_id, api_key)`
  - `as_tools(integration_config)` to produce the tool list (each tool must provide `name` and `description`)

## Usage
```python
from naas_abi_marketplace.applications.algolia.agents.AlgoliaAgent import AlgoliaAgent

agent = AlgoliaAgent.New()
# Use `agent` via IntentAgent interfaces (execution/runtime is defined outside this file).
```

## Caveats
- `New()` asserts the model registry is initialized: `assert registry is not None`.
- Algolia credentials must be available via `ABIModule` configuration; otherwise the created tools may fail at runtime.
- `AlgoliaAgent` adds no custom runtime methods beyond what `IntentAgent` provides; behavior comes from configured tools, intents, and prompt.
