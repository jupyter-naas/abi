# QontoAgent

## What it is
An `IntentAgent` implementation for Qonto-focused assistance. It is configured to provide **general guidance only** (no Qonto tools are wired), with a predefined system prompt and a couple of RAW intents.

## Public API
- `class QontoAgent(IntentAgent)`
  - Agent definition with class attributes:
    - `name = "Qonto"`
    - `description = "Helps you interact with Qonto for business banking and financial management."`
    - `system_prompt`: guidance-only prompt (explicitly states no tool access)
    - `suggestions: list = []`
- `QontoAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> QontoAgent` (classmethod)
  - Factory that:
    - Retrieves default chat and embedding models from the application’s `ModelRegistryService`.
    - Configures:
      - `tools = []`
      - `agents = []`
      - `intents`: two `IntentType.RAW` entries for informational responses.
    - Defaults if not provided:
      - `agent_configuration = AgentConfiguration(system_prompt=QontoAgent.system_prompt)`
      - `agent_shared_state = AgentSharedState(thread_id="0")`
    - Returns a constructed `QontoAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires the Qonto application module:
  - `from naas_abi_marketplace.applications.qonto import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
  - Asserts model registry is initialized: `assert registry is not None`
- Models are pulled from the registry:
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.qonto.agents.QontoAgent import QontoAgent

agent = QontoAgent.New()
# Interact with `agent` via the IntentAgent interface from naas_abi_core.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access Qonto accounts, balances, transactions, or perform banking operations.
- Requires a properly initialized `ABIModule` engine with `model_registry` available; otherwise the factory asserts and fails.
