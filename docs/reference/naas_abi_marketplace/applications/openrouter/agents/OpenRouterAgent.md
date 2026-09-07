# OpenRouterAgent

## What it is
- An `IntentAgent` implementation for the OpenRouter application.
- Provides:
  - A fixed chat model identifier (`MODEL_ID = "openrouter/free"`) exposed via `get_chat_model_id()`.
  - A factory (`New`) that wires up:
    - Chat model (from a model registry if available, otherwise via `OpenRouterModel`)
    - Default embedding model (from the model registry)
    - OpenRouter API tools (via `OpenRouterAPIIntegration.as_tools`)
    - A small set of RAW and TOOL intents

## Public API

### Class: `OpenRouterAgent(IntentAgent)`
- **Class attributes**
  - `name`: `"OpenRouter"`
  - `description`: `"Helps you interact with OpenRouter for accessing multiple AI models."`
  - `MODEL_ID`: `"openrouter/free"` (canonical model id used by this agent)
  - `logo_url`: URL string
  - `suggestions`: `[]`
  - `system_prompt`: system prompt template containing a `[TOOLS]` placeholder

- **Class methods**
  - `get_chat_model_id() -> str | None`
    - Returns `MODEL_ID`.
  - `New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> OpenRouterAgent`
    - Constructs and returns an initialized `OpenRouterAgent`.
    - Model selection:
      - If the engine’s model registry contains a canonical id matching the last path segment of `MODEL_ID` (e.g., `"free"`), uses `registry.get_chat_model(..., provider="openrouter")`.
      - Otherwise uses `OpenRouterModel(api_key).get_model(MODEL_ID)`.
    - Embeddings:
      - Uses `module.engine.services.model_registry.get_default_embedding_model().model`.
    - Tools:
      - Builds tools from `OpenRouterAPIIntegrationConfiguration(api_key, object_storage)` via `as_tools(...)`.
    - Intents:
      - RAW: informational prompts about OpenRouter and routing.
      - TOOL: targets `openrouter_list_models` and `openrouter_list_providers`.
    - System prompt:
      - Replaces `[TOOLS]` with a bullet list of `tool.name: tool.description`.
    - Defaults:
      - Creates `AgentConfiguration(system_prompt=...)` and `AgentSharedState()` if not provided.

## Configuration/Dependencies
- Requires OpenRouter application module initialization:
  - `naas_abi_marketplace.applications.openrouter.ABIModule.get_instance()` must be available.
- Expects services/config provided by the module:
  - `module.configuration.openrouter_api_key`
  - `module.engine.services.object_storage`
  - `module.engine.services.model_registry` (for chat model lookup and default embedding model)
- Depends on:
  - `naas_abi_core.services.agent.IntentAgent` (`IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`)
  - `naas_abi_marketplace.applications.openrouter.models.OpenRouterModel`
  - `naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration`:
    - `OpenRouterAPIIntegrationConfiguration`, `as_tools`
  - `langchain_core.language_models.BaseChatModel` (type usage)

## Usage
```python
from naas_abi_marketplace.applications.openrouter.agents.OpenRouterAgent import OpenRouterAgent

agent = OpenRouterAgent.New()
print(agent.name)
print(agent.get_chat_model_id())
```

## Caveats
- The agent’s model id is fixed to `openrouter/free` via `MODEL_ID`.
- Tool availability and behavior depend on `as_tools(...)` and the runtime module configuration (API key, services).
