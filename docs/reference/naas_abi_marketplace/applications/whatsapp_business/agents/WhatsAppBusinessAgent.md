# WhatsAppBusinessAgent

## What it is
- An `IntentAgent` subclass configured to provide **general guidance** about WhatsApp Business (features, messaging best practices, customer communication).
- Includes a built-in system prompt and a couple of basic informational intents.
- Ships **without tools**, so it cannot execute WhatsApp actions.

## Public API
- `class WhatsAppBusinessAgent(IntentAgent)`
  - Preconfigured agent metadata:
    - `name = "WhatsApp_Business"`
    - `description = "Helps you interact with WhatsApp Business for business messaging and customer communication."`
    - `system_prompt`: multi-section prompt describing role/objectives/constraints (guidance only, no tool access).
    - `suggestions = []` (empty)

- `WhatsAppBusinessAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> WhatsAppBusinessAgent` (classmethod)
  - Factory that constructs and returns a configured `WhatsAppBusinessAgent`.
  - Behavior:
    - Retrieves the default chat and embedding models from the application `ModelRegistryService` via `ABIModule.get_instance()`.
    - Configures:
      - `tools = []`
      - `intents`: two `IntentType.RAW` intents with predefined informational responses.
      - `memory = None`
    - Defaults:
      - If `agent_configuration` is not provided: `AgentConfiguration(system_prompt=cls.system_prompt)`
      - If `agent_shared_state` is not provided: `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Runtime dependency:
  - `naas_abi_marketplace.applications.whatsapp_business.ABIModule`
    - Must provide an initialized engine with `services.model_registry` available.
    - Uses:
      - `registry.get_default_chat_model()`
      - `registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.whatsapp_business.agents.WhatsAppBusinessAgent import (
    WhatsAppBusinessAgent,
)

agent = WhatsAppBusinessAgent.New()
print(agent.name)  # WhatsApp_Business
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot send messages or manage real WhatsApp conversations—only provide general information.
- Requires a properly initialized `ABIModule` with `ModelRegistryService` available; otherwise an assertion will fail (`"ModelRegistryService not initialized"`).
