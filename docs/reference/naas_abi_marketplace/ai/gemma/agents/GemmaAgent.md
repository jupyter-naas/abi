# GemmaAgent

## What it is
A small factory + thin subclass of `IntentAgent` that wires a local **Gemma3 4B** chat model (`gemma3:4b`) from the marketplace `ABIModule` into an agent with a predefined system prompt and a set of simple phrase-based intents that all route to `call_model`.

## Public API
- **Constants**
  - `NAME`: `"Gemma"`
  - `DESCRIPTION`: Human-readable description of the agent/model.
  - `AVATAR_URL`: Avatar image URL.
  - `SYSTEM_PROMPT`: Default system prompt used when no configuration is provided.
  - `SUGGESTIONS`: Empty list.

- **Functions**
  - `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
    - Fetches a chat model from `ABIModule` (`model_registry.get_chat_model("gemma3:4b")`).
    - Defines empty `tools` and `agents` lists.
    - Registers multiple `Intent` entries (`IntentType.AGENT`) mapping trigger phrases (e.g., `"activate gemma"`, `"start private chat"`) to `intent_target="call_model"`.
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided.
      - `AgentSharedState(thread_id="0")` if not provided.
    - Returns a `GemmaAgent` instance with `memory=None`.

- **Classes**
  - `class GemmaAgent(IntentAgent)`
    - No additional behavior (empty subclass).

## Configuration/Dependencies
- **Core types** (imported from `naas_abi_core.services.agent.IntentAgent`):
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- **Model/engine access**
  - `from naas_abi_marketplace.ai.gemma import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry.get_chat_model("gemma3:4b")`
- **Agent wiring choices in this file**
  - `tools = []`
  - `agents = []`
  - `memory = None`

## Usage
```python
from naas_abi_marketplace.ai.gemma.agents.GemmaAgent import create_agent

agent = create_agent()
# Interact with `agent` using the IntentAgent interface from naas_abi_core.
```

## Caveats
- This module only constructs/configures the agent. Intent matching, handling of `intent_target="call_model"`, and execution of the underlying chat model are implemented in `IntentAgent` and the engine/model registry.
