# ZohoAgent

## What it is
A configured `IntentAgent` for providing general guidance about Zoho business applications (including CRM and productivity workflows). It is explicitly **guidance-only** and ships with **no Zoho tools** or data access.

## Public API
- `class ZohoAgent(IntentAgent)`
  - Agent definition with built-in metadata:
    - `name = "Zoho"`
    - `description = "Helps you interact with Zoho for business applications and CRM operations."`
    - `system_prompt`: guidance-oriented prompt that states tools are unavailable.
    - `suggestions: list = []` (empty)

- `ZohoAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> ZohoAgent`
  - Factory/classmethod that constructs and returns a fully configured `ZohoAgent`.
  - Initializes:
    - `chat_model`: from the application’s model registry default chat model
    - `embedding_model`: from the application’s model registry default embedding model (`.model`)
    - `tools`: `[]` (none)
    - `intents`: two `IntentType.RAW` intents with canned guidance text
    - `state`: provided or `AgentSharedState(thread_id="0")`
    - `configuration`: provided or `AgentConfiguration(system_prompt=ZohoAgent.system_prompt)`
    - `memory`: `None`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Depends on the Zoho application module:
  - `from naas_abi_marketplace.applications.zoho import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
  - Requires the model registry service to be initialized (`assert registry is not None`).

## Usage
```python
from naas_abi_marketplace.applications.zoho.agents.ZohoAgent import ZohoAgent

agent = ZohoAgent.New()
print(agent.name)  # "Zoho"
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access Zoho accounts/data or perform actions—only provide general guidance.
- Requires the application engine/model registry to be initialized; otherwise `ZohoAgent.New()` will raise an assertion error (`"ModelRegistryService not initialized"`).
