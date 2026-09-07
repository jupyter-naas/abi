# DataGouvAgent

## What it is
- An `IntentAgent` specialized for **general guidance** about DataGouv (open data/public datasets) and dataset discovery.
- **No tools are configured**, so it cannot retrieve datasets or perform external actions.

## Public API
- `class DataGouvAgent(IntentAgent)`
  - Agent definition with built-in:
    - `name = "DataGouv"`
    - `description = "Helps you interact with DataGouv for open data and public datasets."`
    - `system_prompt` describing scope/constraints (guidance only; no tools)
    - `suggestions = []`

- `DataGouvAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> DataGouvAgent`
  - Factory method that:
    - Resolves default models via the application `ABIModule` model registry:
      - `chat_model = registry.get_default_chat_model()`
      - `embedding_model = registry.get_default_embedding_model().model`
    - Sets `tools = []` (no tool access)
    - Configures two RAW intents:
      - “Get information about DataGouv features”
      - “Understand open data and dataset discovery”
    - Defaults:
      - `AgentConfiguration(system_prompt=DataGouvAgent.system_prompt)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided
    - Returns an initialized `DataGouvAgent` with `memory=None`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on the DataGouv application module:
  - `from naas_abi_marketplace.applications.datagouv import ABIModule`
  - Requires `ABIModule.get_instance().engine.services.model_registry` to be initialized
  - Raises via `assert` if the model registry is missing: `"ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.applications.datagouv.agents.DataGouvAgent import DataGouvAgent

agent = DataGouvAgent.New()
# Use `agent` with your host framework's execution/chat loop for IntentAgent instances.
```

## Caveats
- `tools` is an empty list, so the agent:
  - cannot fetch DataGouv datasets,
  - cannot perform external operations,
  - must remain within guidance-only constraints defined in `system_prompt`.
- `DataGouvAgent.New()` requires a properly initialized `ABIModule` engine/model registry; otherwise it will assert.
