# OpenRouterAgent

## What it is
- An `IntentAgent` factory and concrete agent class for the OpenRouter application.
- Builds an agent with:
  - An OpenRouter-backed chat model (`openrouter/free`)
  - OpenRouter API tools (via `OpenRouterAPIIntegration.as_tools`)
  - A fixed set of intents (some informational, some tool-backed)

## Public API

### Constants
- `NAME`: `"OpenRouter"`
- `DESCRIPTION`: Human-readable agent description.
- `SYSTEM_PROMPT`: Base system prompt template (injects tool list at `[TOOLS]`).
- `SUGGESTIONS`: Empty list (no suggestions configured).

### Functions
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Creates and returns an initialized `OpenRouterAgent`.
  - Pulls configuration and services from `ABIModule.get_instance()`:
    - `module.configuration.openrouter_api_key`
    - `module.engine.services.object_storage`
  - Configures:
    - Chat model: `OpenRouterModel(api_key).get_model("openrouter/free")`
    - Tools: `as_tools(OpenRouterAPIIntegrationConfiguration(api_key, object_storage))`
    - Intents:
      - Informational RAW intents (general guidance)
      - TOOL intents targeting:
        - `openrouter_list_models`
        - `openrouter_list_providers`

### Classes
- `class OpenRouterAgent(IntentAgent)`
  - A thin subclass of `IntentAgent` with class attributes:
    - `name`, `description`, `logo_url`, `suggestions`

## Configuration/Dependencies
- Requires `ABIModule` to be initialized and able to provide:
  - `openrouter_api_key` in `module.configuration`
  - `object_storage` in `module.engine.services`
- Depends on:
  - `naas_abi_core.services.agent.IntentAgent` (`IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`)
  - `naas_abi_marketplace.applications.openrouter.models.OpenRouterModel`
  - `naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration`:
    - `OpenRouterAPIIntegrationConfiguration`
    - `as_tools`

## Usage
```python
from naas_abi_marketplace.applications.openrouter.agents.OpenRouterAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent instance (OpenRouterAgent subclass)
print(agent.name)
print(agent.description)
```

## Caveats
- The system prompt explicitly states limited capabilities without tools; actual tool availability depends on `as_tools(...)` and runtime configuration.
- The model is hard-coded to `"openrouter/free"` in this factory.
