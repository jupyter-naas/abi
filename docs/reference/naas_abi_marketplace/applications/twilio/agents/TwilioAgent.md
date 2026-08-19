# TwilioAgent

## What it is
- An `IntentAgent` implementation focused on **Twilio communication services** (SMS, voice, messaging).
- Provides **information and guidance only**; it **does not** execute Twilio operations because **no tools are configured**.

## Public API
- `class TwilioAgent(IntentAgent)`
  - Agent metadata (class attributes):
    - `name = "Twilio"`
    - `description = "Helps you interact with Twilio for communication services and messaging."`
    - `system_prompt`: instructions emphasizing guidance-only behavior (no tools)
    - `suggestions = []`
- `TwilioAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> TwilioAgent`
  - Factory constructor that:
    - Fetches default chat and embedding models from the module engine’s `model_registry`.
    - Sets `tools = []` and defines two RAW intents:
      - “Get information about Twilio features”
      - “Understand messaging and voice communication”
    - Defaults:
      - `AgentConfiguration(system_prompt=TwilioAgent.system_prompt)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided
    - Returns a configured `TwilioAgent` with `memory=None`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Requires Twilio application module wiring:
  - `from naas_abi_marketplace.applications.twilio import ABIModule`
  - `ABIModule.get_instance().engine.services.model_registry` must be initialized
    - Uses:
      - `registry.get_default_chat_model()`
      - `registry.get_default_embedding_model().model`
- No external Twilio SDK usage in this file.

## Usage
```python
from naas_abi_marketplace.applications.twilio.agents.TwilioAgent import TwilioAgent

agent = TwilioAgent.New()
print(agent.name)         # Twilio
print(agent.description)  # Helps you interact with Twilio for communication services and messaging.
```

## Caveats
- **No tools are configured** (`tools = []`), so the agent:
  - cannot send SMS, place calls, or interact with Twilio APIs
  - should only provide general guidance per `system_prompt`
- Construction asserts that a model registry exists:
  - `assert registry is not None, "ModelRegistryService not initialized"`
