# DeepSeekAgent

## What it is
A minimal agent factory and `IntentAgent` subclass that wires a local **DeepSeek R1 8B** chat model (via Ollama) into the `naas_abi_core` intent-based agent framework, with a reasoning/math/science-oriented system prompt and a predefined set of intent triggers.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `DeepSeekAgent`:
    - Loads the DeepSeek model from `naas_abi_marketplace.ai.deepseek.models.deepseek_r1_8b`.
    - Registers a list of `Intent` entries that route to the `"call_model"` target.
    - Applies default `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if none provided.
    - Applies default `AgentSharedState(thread_id="0")` if none provided.
    - Uses no tools, no sub-agents, and `memory=None`.

- `class DeepSeekAgent(IntentAgent)`
  - Empty subclass of `IntentAgent` (no additional behavior defined here).

### Module-level constants
- `NAME`: `"DeepSeek"`
- `DESCRIPTION`: `"Local DeepSeek R1 8B model via Ollama - advanced reasoning, mathematics, and problem-solving"`
- `AVATAR_URL`: URL string for an avatar image
- `SYSTEM_PROMPT`: multi-section prompt describing reasoning/math/science focus and response style
- `SUGGESTIONS`: empty list

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on a model definition:
  - `naas_abi_marketplace.ai.deepseek.models.deepseek_r1_8b` (imports `model`)
- Default configuration applied by `create_agent`:
  - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
  - `AgentSharedState(thread_id="0")`

## Usage
```python
from naas_abi_marketplace.ai.deepseek.agents.DeepSeekAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent (specifically DeepSeekAgent)
print(type(agent).__name__)
print(agent.name)
```

## Caveats
- This module does not define runtime execution methods; it only constructs the agent object and intent mappings. Actual message handling depends on `IntentAgent` implementation in `naas_abi_core`.
- Tools, sub-agents, and memory are explicitly set to empty/`None` in `create_agent`.
