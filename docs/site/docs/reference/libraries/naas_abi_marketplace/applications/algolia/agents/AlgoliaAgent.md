# AlgoliaAgent

## What it is
- A thin `IntentAgent` wrapper configured to interact with Algolia via marketplace-provided integration tools.
- Provides a factory (`create_agent`) that wires:
  - Algolia credentials from the Algolia `ABIModule` configuration
  - A ChatGPT model (`gpt_4_1_mini`)
  - Algolia tool bindings (search, add records, list indexes, index stats)
  - A system prompt that embeds available tools

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Builds and returns an `AlgoliaAgent` instance with tools, intents, model, and prompt configured.
  - If `agent_shared_state` is not provided, defaults to `AgentSharedState(thread_id="0")`.
  - If `agent_configuration` is not provided, defaults to `AgentConfiguration(system_prompt=...)`.

- `class AlgoliaAgent(IntentAgent)`
  - Concrete agent class; adds no additional methods/behavior beyond `IntentAgent`.

## Configuration/Dependencies
- Requires the Algolia application module:
  - `naas_abi_marketplace.applications.algolia.ABIModule.get_instance()`
  - Uses `module.configuration.algolia_api_key` and `module.configuration.algolia_application_id`
- Uses model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
- Uses integration tooling:
  - `AlgoliaIntegrationConfiguration(app_id, api_key)`
  - `as_tools(integration_config)` to produce tool objects
- Exposed intents (tool targets):
  - `algolia_search`
  - `algolia_add_record`
  - `algolia_list_indexes`
  - `algolia_index_stats`

## Usage
```python
from naas_abi_marketplace.applications.algolia.agents.AlgoliaAgent import create_agent

agent = create_agent()
# Agent can then be used via IntentAgent's runtime/execution interfaces (not defined in this file).
```

## Caveats
- The agent relies on Algolia credentials being available via the Algolia `ABIModule` configuration; missing/invalid credentials may prevent tools from working.
- The `AlgoliaAgent` class itself is empty (`pass`); all behavior comes from `IntentAgent` and the configured tools/intents.
