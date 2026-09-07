# GrokAgent

## What it is
A small factory module that creates a preconfigured `IntentAgent` instance named **Grok**, with a fixed system prompt and a set of intent phrases routed to the agent’s `"call_model"` target.

## Public API
- **Constants**
  - `NAME`: `"Grok"`
  - `DESCRIPTION`: Agent description string
  - `AVATAR_URL`: Avatar image URL
  - `SYSTEM_PROMPT`: System prompt used when no configuration is provided
  - `SUGGESTIONS`: Empty list (`[]`)

- **Functions**
  - `create_agent(agent_configuration: AgentConfiguration | None = None, agent_shared_state: AgentSharedState | None = None) -> IntentAgent`
    - Loads chat model `"grok-4"` from the marketplace module engine model registry.
    - Builds an `IntentAgent` with:
      - no tools (`tools = []`)
      - no sub-agents (`agents = []`)
      - a predefined list of `Intent` entries (all `IntentType.AGENT` targeting `"call_model"`)
    - Applies defaults if parameters are not provided:
      - `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
      - `AgentSharedState(thread_id="0")`

- **Classes**
  - `class GrokAgent(IntentAgent)`
    - No additional methods/overrides; inherits all behavior from `IntentAgent`.

## Configuration/Dependencies
- **Imports / dependencies**
  - `naas_abi_core.services.agent.IntentAgent`:
    - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
  - `naas_abi_marketplace.ai.grok.ABIModule`:
    - Used to fetch `chat_model` via `abi_module.engine.services.model_registry.get_chat_model("grok-4")`

- **Intent routing**
  - The following intent values are registered, each with `intent_type=IntentType.AGENT` and `intent_target="call_model"`:
    - `"search news about"`
    - `"search web about"`
    - `"search information about"`
    - `"analyze scientific problems"`
    - `"think critically"`
    - `"seek truth"`
    - `"challenge conventional views"`
    - `"reason rigorously"`

## Usage
```python
from naas_abi_marketplace.ai.grok.agents.GrokAgent import create_agent

agent = create_agent()
# Use the returned IntentAgent via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- `GrokAgent` adds no custom behavior; functionality depends entirely on `IntentAgent` and the `"grok-4"` model returned by the model registry.
- Intent dispatch behavior for `"call_model"` is defined by `IntentAgent` (not in this module).
