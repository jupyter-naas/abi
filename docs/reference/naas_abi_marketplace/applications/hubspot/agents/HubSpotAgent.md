# HubSpotAgent

## What it is
A HubSpot-focused `IntentAgent` that provides general guidance on HubSpot CRM, marketing automation, and sales pipeline management. It does **not** include any HubSpot tools/integrations, so it cannot access or modify HubSpot data.

## Public API
- `class HubSpotAgent(IntentAgent)`
  - Preconfigured agent metadata:
    - `name = "HubSpot"`
    - `description = "Helps you interact with HubSpot for CRM, marketing, and sales operations."`
    - `system_prompt`: guidance-only prompt explicitly stating no tool access
    - `suggestions = []`

- `HubSpotAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> HubSpotAgent` (classmethod)
  - Factory that builds and returns a configured `HubSpotAgent`.
  - Behavior:
    - Retrieves the default chat and embedding models from the application `ModelRegistryService`.
    - Configures:
      - `tools = []`
      - `agents = []`
      - `intents`: two predefined `IntentType.RAW` intents with static informational responses.
    - Defaults:
      - If `agent_configuration` is `None`: `AgentConfiguration(system_prompt=HubSpotAgent.system_prompt)`
      - If `agent_shared_state` is `None`: `AgentSharedState(thread_id="0")`
    - Returns an `IntentAgent` instance with `memory=None`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Depends on HubSpot application module for model access:
  - `from naas_abi_marketplace.applications.hubspot import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
  - Requires the `ModelRegistryService` to be initialized (`assert registry is not None`)
- Models:
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`
- Tools:
  - None (`tools = []`)

## Usage
```python
from naas_abi_marketplace.applications.hubspot.agents.HubSpotAgent import HubSpotAgent

agent = HubSpotAgent.New()
# Interact with `agent` through the IntentAgent APIs provided by your runtime/framework.
```

## Caveats
- No HubSpot tools are configured; the agent cannot access CRM objects (contacts, deals, etc.) or perform operations.
- The built-in intents are static RAW responses and do not query external systems.
