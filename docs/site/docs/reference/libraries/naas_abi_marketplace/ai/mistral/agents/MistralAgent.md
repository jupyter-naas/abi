# MistralAgent

## What it is
A thin wrapper around `naas_abi_core`’s `IntentAgent` configured to use the Mistral Large model with a predefined system prompt and a small set of coding/documentation-related intents.

## Public API
- **Constants**
  - `AVATAR_URL`: Public avatar image URL.
  - `NAME`: `"Mistral"`.
  - `DESCRIPTION`: Short description of the agent/model.
  - `SYSTEM_PROMPT`: System prompt defining behavior and “self-recognition” rules.
  - `SUGGESTIONS`: Empty list (no suggestions provided).

- **Functions**
  - `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
    - Creates and returns a configured `MistralAgent`.
    - Defaults:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)` if not provided.
      - `AgentSharedState(thread_id="0")` if not provided.
    - Registers intents that target `call_model` for:
      - generate code, review code, optimize code, document technical details, help with programming.

- **Classes**
  - `class MistralAgent(IntentAgent)`
    - No additional methods/overrides; inherits behavior from `IntentAgent`.

## Configuration/Dependencies
- **Depends on `naas_abi_core.services.agent.IntentAgent`**:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`.
- **Model import**
  - Imports `model` from `naas_abi_marketplace.ai.mistral.models.mistral_large_2411` and passes `model.model` as `chat_model`.
- **Tools/Agents**
  - `tools` and `agents` are empty lists in this implementation.
- **Memory**
  - `memory=None` is passed to the agent constructor.

## Usage
```python
from naas_abi_marketplace.ai.mistral.agents.MistralAgent import create_agent

agent = create_agent()
# Use `agent` via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- `MistralAgent` adds no custom logic; all runtime behavior comes from `IntentAgent` and the imported chat model.
- The registered intents all target `"call_model"`; this relies on the underlying `IntentAgent` implementation to route that target correctly.
