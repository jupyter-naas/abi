# QwenAgent

## What it is
A thin wrapper that constructs an `IntentAgent` configured for the local **Qwen3 8B** chat model (via Ollama) with a predefined system prompt and a set of intents focused on coding, privacy/local usage, multilingual help, and reasoning.

## Public API
- **Constants**
  - `NAME`: Agent display name (`"Qwen"`).
  - `DESCRIPTION`: Human-readable description of the agent.
  - `AVATAR_URL`: URL to an avatar image.
  - `SYSTEM_PROMPT`: Default system prompt describing capabilities and response style.
  - `SUGGESTIONS`: Empty list (no default suggestions).

- **Functions**
  - `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
    - Creates and returns a configured `QwenAgent`.
    - Loads the chat model from `naas_abi_marketplace.ai.qwen.models.qwen3_8b`.
    - Defines a list of `Intent` objects targeting `"call_model"`.
    - If not provided:
      - Creates `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
      - Creates `AgentSharedState(thread_id="0")`

- **Classes**
  - `class QwenAgent(IntentAgent)`
    - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `Intent`, `IntentType`, `AgentConfiguration`, `AgentSharedState`
- Loads the model dynamically inside `create_agent`:
  - `from naas_abi_marketplace.ai.qwen.models.qwen3_8b import model`
- Tools and sub-agents are currently empty lists (`tools = []`, `agents = []`).

## Usage
```python
from naas_abi_marketplace.ai.qwen.agents.QwenAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent (specifically QwenAgent) configured with:
# - system prompt (SYSTEM_PROMPT)
# - chat model (qwen3_8b model)
# - a predefined set of intents targeting "call_model"
print(type(agent).__name__)
```

## Caveats
- `QwenAgent` itself adds no methods; all behavior comes from `IntentAgent`.
- The function assumes `naas_abi_marketplace.ai.qwen.models.qwen3_8b.model` is importable and correctly configured.
