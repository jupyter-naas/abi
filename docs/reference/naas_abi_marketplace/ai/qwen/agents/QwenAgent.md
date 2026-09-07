# QwenAgent

## What it is
A small factory and wrapper around `IntentAgent` that creates an agent named **Qwen**, configured to use a locally-registered Qwen chat model (`CanonicalModelId.QWEN_3_6`) and a predefined system prompt focused on privacy, coding, multilingual help, and reasoning.

## Public API

- **Constants**
  - `NAME`: `"Qwen"`
  - `DESCRIPTION`: Agent description string.
  - `AVATAR_URL`: Avatar image URL.
  - `SYSTEM_PROMPT`: Default system prompt used when no configuration is provided.
  - `SUGGESTIONS`: Empty list (`[]`).

- **Function**
  - `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
    - Builds and returns a `QwenAgent` (an `IntentAgent` subclass).
    - Retrieves the chat model from the ABI module model registry using `CanonicalModelId.QWEN_3_6`.
    - Registers a fixed list of `Intent` items with `intent_type=IntentType.AGENT` and `intent_target="call_model"`.
    - If not provided:
      - `agent_configuration` defaults to `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
      - `agent_shared_state` defaults to `AgentSharedState(thread_id="0")`
    - Creates the agent with `tools=[]`, `agents=[]`, and `memory=None`.

- **Class**
  - `class QwenAgent(IntentAgent)`
    - Empty subclass; adds no additional behavior beyond `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `CanonicalModelId`
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Requires `naas_abi_marketplace.ai.qwen.ABIModule`:
  - Used to access `abi_module.engine.services.model_registry.get_chat_model(CanonicalModelId.QWEN_3_6)`.

## Usage
```python
from naas_abi_marketplace.ai.qwen.agents.QwenAgent import create_agent

agent = create_agent()
print(agent.name)  # "Qwen"
```

## Caveats
- `QwenAgent` adds no methods; all runtime behavior comes from `IntentAgent`.
- `create_agent()` assumes `ABIModule.get_instance()` is available and that the model registry can resolve `CanonicalModelId.QWEN_3_6`.
