# DeepSeekAgent

## What it is
A small factory and `IntentAgent` subclass that wires a local **DeepSeek R1 8B** chat model (via the ABI model registry) into the `naas_abi_core` intent-based agent framework, with a reasoning/math/science-oriented system prompt and predefined intent triggers.

## Public API

### Functions
- `create_agent(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> IntentAgent`
  - Builds and returns a configured `DeepSeekAgent`.
  - Retrieves the chat model from the ABI model registry: `get_chat_model("deepseek-r1:8b")`.
  - Registers a fixed list of `Intent` entries that target `"call_model"`.
  - Defaults:
    - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` when `agent_configuration` is `None`
    - `AgentSharedState(thread_id="0")` when `agent_shared_state` is `None`
  - Sets:
    - `tools = []`
    - `agents = []`
    - `memory = None`

### Classes
- `class DeepSeekAgent(IntentAgent)`
  - Empty subclass (no additional behavior beyond `IntentAgent`).

### Module constants
- `NAME`: `"DeepSeek"`
- `DESCRIPTION`: `"Local DeepSeek R1 8B model via Ollama - advanced reasoning, mathematics, and problem-solving"`
- `AVATAR_URL`: `"https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/deepseek.png"`
- `SYSTEM_PROMPT`: multi-section prompt focused on systematic reasoning, math, and scientific analysis
- `SUGGESTIONS`: empty list (`[]`)

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on the DeepSeek ABI module singleton:
  - `from naas_abi_marketplace.ai.deepseek import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry.get_chat_model("deepseek-r1:8b")`

## Usage
```python
from naas_abi_marketplace.ai.deepseek.agents.DeepSeekAgent import create_agent

agent = create_agent()

print(type(agent).__name__)  # DeepSeekAgent
print(agent.name)            # DeepSeek
```

## Caveats
- This module only constructs the agent, intent mappings, and configuration; actual execution/routing behavior depends on `IntentAgent` in `naas_abi_core`.
- No tools, sub-agents, or memory are configured (`tools=[]`, `agents=[]`, `memory=None`).
- Model retrieval assumes the ABI runtime has a chat model registered under `"deepseek-r1:8b"`.
