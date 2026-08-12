# LlamaAgent

## What it is
A thin wrapper around `IntentAgent` that instantiates an agent named **Llama**, configured with a Llama chat model (`CanonicalModelId.LLAMA_3_3_70B`), a predefined system prompt, and a fixed set of intents that all target `"call_model"`.

## Public API
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
  - Creates and returns a configured `LlamaAgent`.
  - Behavior:
    - Resolves the chat model via `ABIModule.get_instance().engine.services.model_registry.get_chat_model(CanonicalModelId.LLAMA_3_3_70B)`.
    - Configures:
      - `tools = []`
      - `agents = []`
      - `intents`: `general knowledge`, `conversation`, `writing assistance`, `creative tasks`, `brainstorming`, `help me write python code` (all `IntentType.AGENT`, `intent_target="call_model"`).
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if `agent_configuration` is `None`.
      - `AgentSharedState(thread_id="0")` if `agent_shared_state` is `None`.
    - Sets `memory=None`.

- `class LlamaAgent(IntentAgent)`
  - No overrides; inherits all behavior from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on `naas_abi_core.models.Model.CanonicalModelId`:
  - Uses `CanonicalModelId.LLAMA_3_3_70B`
- Depends on `naas_abi_marketplace.ai.llama.ABIModule`:
  - Used to access `model_registry` and retrieve the chat model
- Module constants:
  - `NAME`, `DESCRIPTION`, `AVATAR_URL`, `SYSTEM_PROMPT`, `SUGGESTIONS` (empty list)

## Usage
```python
from naas_abi_marketplace.ai.llama.agents.LlamaAgent import create_agent

agent = create_agent()
# agent is an IntentAgent instance (LlamaAgent) configured with LLAMA_3_3_70B and preset intents.
```

## Caveats
- `LlamaAgent` adds no custom logic; runtime behavior is determined by `IntentAgent` and the resolved chat model.
- No tools or sub-agents are configured (`tools=[]`, `agents=[]`).
- Requires `ABIModule` and its engine/model registry to be initialized/available to resolve the chat model.
