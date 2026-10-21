# OpenRouterAgents

## What it is
- A factory that lists OpenRouter models and dynamically generates one `Agent` subclass per eligible model.
- Each generated agent class provides a `New(...)` constructor and exposes the model id via `get_chat_model_id()` without instantiation.

## Public API
- `class OpenRouterAgents(openrouter_integration: OpenRouterAPIIntegration, openrouter_model: OpenRouterModel)`
  - Stores dependencies used to list models and build chat model instances.

- `create_agents(include_models: list[str] | None = None) -> list[type[Agent]]`
  - Fetches models via `openrouter_integration.list_models(save_json=False)`.
  - Optionally filters to `include_models` by exact match on `model_data["id"]`.
  - Returns dynamically created `Agent` subclasses for models that:
    - include `"text"` in `model_data["architecture"]["input_modalities"]`, **and**
    - include `"tools"` in `model_data["supported_parameters"]`.

### Generated agent classes (returned by `create_agents`)
Each generated class:
- Inherits from `naas_abi_core.services.agent.Agent.Agent`.
- Has class attributes:
  - `name`, `description`, `logo_url`, `MODEL_ID`
- Has class methods:
  - `get_chat_model_id() -> str | None` (returns `MODEL_ID`)
  - `New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> Agent`
    - Builds/uses a chat model:
      - First attempts `ABIModule.get_instance().engine.services.model_registry` lookup using the last path segment of `MODEL_ID` (e.g. `"anthropic/claude"` → `"claude"`) and `provider="openrouter"`.
      - Otherwise falls back to `openrouter_model.get_model(MODEL_ID)`.
    - If `agent_configuration` is not provided, constructs a default `AgentConfiguration(system_prompt=...)` using fields from the model dict (context length, architecture fields, pricing).
    - If `agent_shared_state` is not provided, constructs a new `AgentSharedState()`.
    - Instantiates the agent with `tools=[]`, `agents=[]`, and `memory=None`.

## Configuration/Dependencies
- Requires:
  - `OpenRouterAPIIntegration`
    - Must implement `list_models(save_json=False)` returning a list of model dicts.
  - `OpenRouterModel`
    - Must implement `get_model(model_id)` returning a chat model compatible with `Agent`.
  - `naas_abi_core` agent types:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `ABIModule` (imported at runtime inside `New`) to access `engine.services.model_registry`.
- Assets:
  - Provider logos are searched locally under: `.../applications/openrouter/assets/public`
  - Filenames: `{provider}-logo-square.(png|jpg|jpeg|svg)` where `provider` is the prefix before `/` in `model_id`.
  - If not found, falls back to `model_data["logo_url"]` if present.
- Logging:
  - Uses `naas_abi_core.logger` for info/warning/error messages.

## Usage
```python
from naas_abi_marketplace.applications.openrouter.agents.OpenRouterAgents import OpenRouterAgents
from naas_abi_marketplace.applications.openrouter.integrations.OpenRouterAPIIntegration import OpenRouterAPIIntegration
from naas_abi_marketplace.applications.openrouter.models.OpenRouterModel import OpenRouterModel

integration = OpenRouterAPIIntegration()
openrouter_model = OpenRouterModel()

factory = OpenRouterAgents(integration, openrouter_model)

agent_classes = factory.create_agents(include_models=["anthropic/claude-3.5-sonnet"])

if agent_classes:
    AgentCls = agent_classes[0]
    print(AgentCls.get_chat_model_id(), AgentCls.name)
    agent = AgentCls.New()
```

## Caveats
- Only models supporting **text input** and listing `"tools"` in `supported_parameters` are turned into agents; others are silently skipped.
- `New()` imports and uses `ABIModule` at call time; if the module/engine/registry is not initialized, instantiation may fail.
- `create_agents()` catches and logs errors:
  - Model listing failures return `[]`.
  - Per-model generation failures skip only the failing model.
