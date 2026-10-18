# GemmaAgent

## What it is
A thin `IntentAgent` wrapper that configures a local **Gemma3 4B** chat model (via the marketplace model module) with a predefined system prompt and a set of conversation/intention triggers.

## Public API
- **Constants**
  - `NAME`: Agent display name (`"Gemma"`).
  - `DESCRIPTION`: Short description of the agent/model.
  - `AVATAR_URL`: Avatar image URL.
  - `SYSTEM_PROMPT`: Default system prompt describing behavior/style.
  - `SUGGESTIONS`: Empty list (no suggestions defined).

- **Functions**
  - `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
    - Builds and returns a configured `GemmaAgent`.
    - Loads the chat model from `naas_abi_marketplace.ai.gemma.models.gemma3_4b`.
    - Registers a set of `Intent` entries mapping various phrases to `intent_target="call_model"`.
    - If not provided:
      - Creates `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
      - Creates `AgentSharedState(thread_id="0")`

- **Classes**
  - `GemmaAgent(IntentAgent)`
    - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Depends on core agent framework types:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`.
- Depends on the Gemma model module:
  - `naas_abi_marketplace.ai.gemma.models.gemma3_4b` (used as `model.model` when passed to `chat_model`).
- Tools/agents/memory:
  - `tools = []`, `agents = []`, `memory = None` (no extensions configured in this file).

## Usage
```python
from naas_abi_marketplace.ai.gemma.agents.GemmaAgent import create_agent

agent = create_agent()
# Use `agent` according to the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- This module only **constructs** the agent; actual runtime behavior (e.g., how `call_model` is invoked, how intents are matched, and how the model is executed via Ollama) is handled by `IntentAgent` and the imported model module.
