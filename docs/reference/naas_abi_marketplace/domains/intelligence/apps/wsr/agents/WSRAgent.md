# WSRAgent

## What it is
- `WSRAgent` is an `IntentAgent` implementation for the “World Situation Room” (WSR) geospatial intelligence app.
- It provides a predefined **system prompt** and a small set of **raw intents** describing common WSR queries (global brief, conflict zones, military flights, earthquakes).
- The `New()` factory builds the agent using default chat/embedding models from the app’s module registry.

## Public API
- **Class `WSRAgent(IntentAgent)`**
  - **Class attributes**
    - `name`: Display name (`"World Situation Room"`).
    - `description`: App description (real-time geospatial intelligence platform).
    - `logo_url`: Logo URL.
    - `system_prompt`: Detailed operating prompt describing data layers, refresh intervals, tasks, and constraints.
    - `intents`: List of `Intent` entries (all `IntentType.RAW`) with predefined responses.
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> WSRAgent`**
    - Purpose: Construct a ready-to-use `WSRAgent`.
    - Behavior:
      - Fetches the default chat model and embedding model from the app’s `ModelRegistryService`.
      - Applies defaults if not provided:
        - `AgentConfiguration(system_prompt=WSRAgent.system_prompt)`
        - `AgentSharedState(thread_id="0")`
      - Instantiates `WSRAgent` with `tools=[]` and `memory=None`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` types:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentSharedState`, `AgentConfiguration`.
- Requires marketplace module wiring:
  - `from naas_abi_marketplace.domains.intelligence.apps.wsr import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
    - Must be initialized and non-`None` (asserted in `New()`).
- Model expectations:
  - `registry.get_default_chat_model()`
  - `registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.domains.intelligence.apps.wsr.agents.WSRAgent import WSRAgent

agent = WSRAgent.New()
print(agent.name)
```

## Caveats
- `WSRAgent.New()` will raise an `AssertionError` if `ModelRegistryService` is not initialized (`model_registry is None`).
- The agent is constructed with `tools=[]` and `memory=None` (no tool integrations or memory configured here).
