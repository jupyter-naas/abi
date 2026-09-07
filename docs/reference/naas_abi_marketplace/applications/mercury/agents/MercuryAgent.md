# MercuryAgent

## What it is
- An `IntentAgent` implementation for providing general guidance about Mercury (banking/financial operations).
- Configured with a static system prompt and two RAW intents.
- Does not configure any Mercury tools (`tools = []`), so it cannot access accounts or perform actions.

## Public API
- `class MercuryAgent(IntentAgent)`
  - Agent definition with class attributes:
    - `name = "Mercury"`
    - `description = "Helps you interact with Mercury for banking and financial operations."`
    - `system_prompt` (multi-line prompt describing scope/constraints)
    - `suggestions = []`
- `MercuryAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> MercuryAgent`
  - Class factory that constructs and returns a configured `MercuryAgent`.
  - Behavior:
    - Loads the Mercury `ABIModule` singleton and pulls models from the engine model registry:
      - `chat_model = registry.get_default_chat_model()`
      - `embedding_model = registry.get_default_embedding_model().model`
    - Sets:
      - `tools = []`
      - `intents` to two `IntentType.RAW` entries about Mercury features and banking/account management
    - Defaults:
      - `agent_configuration = AgentConfiguration(system_prompt=MercuryAgent.system_prompt)` if not provided
      - `agent_shared_state = AgentSharedState(thread_id="0")` if not provided
    - Returns `MercuryAgent(..., memory=None)`

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Requires Mercury application module:
  - `from naas_abi_marketplace.applications.mercury import ABIModule`
- Requires an initialized model registry:
  - `abi_module.engine.services.model_registry` must be set; otherwise an assertion fails.
- Models:
  - Uses default chat and embedding models from the registry.

## Usage
```python
from naas_abi_marketplace.applications.mercury.agents.MercuryAgent import MercuryAgent

agent = MercuryAgent.New()
# Interact with `agent` via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access Mercury data or execute banking operations; it only provides general information and guidance.
- `MercuryAgent.New()` asserts the engine model registry is initialized; it will raise an `AssertionError` if not.
