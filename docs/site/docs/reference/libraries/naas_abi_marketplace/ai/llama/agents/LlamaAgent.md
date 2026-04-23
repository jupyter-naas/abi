# LlamaAgent

## What it is
A thin `IntentAgent` wrapper that configures an agent named **Llama** using a Llama chat model (`llama_3_3_70b`) plus a system prompt and a fixed set of intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `LlamaAgent` instance.
  - Defaults:
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided.
    - `AgentSharedState(thread_id="0")` if not provided.
  - Uses:
    - Chat model imported from `naas_abi_marketplace.ai.llama.models.llama_3_3_70b`.
    - No tools (`tools = []`) and no sub-agents (`agents = []`).
    - Predefined intents targeting `"call_model"`.

- `class LlamaAgent(IntentAgent)`
  - Subclass of `IntentAgent` with no additional methods/overrides (inherits all behavior from `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on `naas_abi_marketplace.ai.llama.models.llama_3_3_70b` for:
  - `model` (used as `chat_model`)
- Key module-level constants:
  - `NAME`, `DESCRIPTION`, `AVATAR_URL`, `SYSTEM_PROMPT`, `SUGGESTIONS` (empty list)
- Intents configured (all `IntentType.AGENT`, `intent_target="call_model"`):
  - `"general knowledge"`, `"conversation"`, `"writing assistance"`, `"creative tasks"`, `"brainstorming"`, `"help me write python code"`

## Usage
```python
from naas_abi_marketplace.ai.llama.agents.LlamaAgent import create_agent

agent = create_agent()
# agent is an IntentAgent (specifically a LlamaAgent) configured with the Llama model and intents.
```

## Caveats
- `LlamaAgent` adds no new behavior; all runtime behavior depends on the inherited `IntentAgent` implementation and the imported `model`.
- No tools or sub-agents are configured (`tools=[]`, `agents=[]`).
