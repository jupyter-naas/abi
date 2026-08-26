# WorldBankAgent

## What it is
A lightweight `IntentAgent` specialized in providing guidance about World Bank economic/development data and indicators. It does **not** include any tools to fetch or query real data.

## Public API
- `class WorldBankAgent(IntentAgent)`
  - Agent definition with fixed metadata:
    - `name = "WorldBank"`
    - `description = "Helps you interact with World Bank data for economic and development indicators."`
    - `system_prompt`: guidance-only; explicitly states no tool access
    - `suggestions = []`

- `WorldBankAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> WorldBankAgent`
  - Factory constructor that:
    - Loads the default chat model and embedding model from the app `ABIModule` model registry
    - Configures:
      - `tools = []`
      - `intents`: two `IntentType.RAW` intents (features overview; indicator concepts)
      - `memory = None`
    - Defaults when not provided:
      - `agent_configuration = AgentConfiguration(system_prompt=WorldBankAgent.system_prompt)`
      - `agent_shared_state = AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires `naas_abi_marketplace.applications.worldbank.ABIModule` to be initialized and to provide:
  - `engine.services.model_registry.get_default_chat_model()`
  - `engine.services.model_registry.get_default_embedding_model()`
- Model registry must exist; otherwise an assertion is raised:
  - `assert registry is not None, "ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.applications.worldbank.agents.WorldBankAgent import WorldBankAgent

agent = WorldBankAgent.New()
# Use `agent` via the IntentAgent interface provided by naas_abi_core
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot retrieve World Bank data.
- Construction requires a working `ABIModule` and initialized `ModelRegistryService`; otherwise `New()` will fail with an assertion.
