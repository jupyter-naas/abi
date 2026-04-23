# GrokAgent

## What it is
A thin wrapper around `naas_abi_core.services.agent.IntentAgent` that instantiates a “Grok” intent-based agent with a predefined system prompt, metadata, and a set of intents that route to `call_model`.

## Public API
- **Constants**
  - `NAME`: Agent display name (`"Grok"`).
  - `DESCRIPTION`: Human-readable description.
  - `AVATAR_URL`: URL to an avatar image.
  - `SYSTEM_PROMPT`: Long-form system prompt that defines behavior/style.
  - `SUGGESTIONS`: Empty list placeholder.

- **Functions**
  - `create_agent(agent_configuration: Optional[AgentConfiguration] = None, agent_shared_state: Optional[AgentSharedState] = None) -> IntentAgent`
    - Builds and returns a configured `GrokAgent`.
    - Loads the chat model from `naas_abi_marketplace.ai.grok.models.grok_4`.
    - Creates a fixed set of `Intent` entries whose `intent_target` is `"call_model"`.

- **Classes**
  - `class GrokAgent(IntentAgent)`
    - No additional behavior; inherits all functionality from `IntentAgent`.

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.services.agent.IntentAgent`:
    - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
  - Chat model import (required at runtime):
    - `from naas_abi_marketplace.ai.grok.models.grok_4 import model`

- **Default configuration**
  - If `agent_configuration` is not provided:
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
  - If `agent_shared_state` is not provided:
    - `AgentSharedState(thread_id="0")`

- **Tools/Agents/Memory**
  - `tools`: empty list
  - `agents`: empty list
  - `memory`: `None`

## Usage
```python
from naas_abi_marketplace.ai.grok.agents.GrokAgent import create_agent

agent = create_agent()

# Interact using IntentAgent's interface (methods depend on IntentAgent implementation).
# Example placeholder:
# response = agent.call_model("search news about space missions")
# print(response)
```

## Caveats
- This module does not implement any custom logic in `GrokAgent`; all behavior depends on `IntentAgent` and the imported `model`.
- The listed intents route to the target string `"call_model"`; actual dispatch behavior depends on `IntentAgent`’s implementation.
