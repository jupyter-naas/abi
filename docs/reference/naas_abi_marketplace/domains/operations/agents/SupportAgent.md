# SupportAgent

## What it is
- `SupportAgent` is an `Agent` specialization for handling support requests.
- It provides:
  - Metadata (`name`, `description`, `logo_url`)
  - A `system_prompt` template with a `[TOOLS]` placeholder
  - Preset `suggestions` for feature requests and bug reports
- It includes message hook methods intended as lightweight observation points.

## Public API
- **Class: `SupportAgent(Agent)`**
  - **Class attributes**
    - `name`: `"Support"`
    - `description`: support scope and issue/feedback focus
    - `logo_url`: `"naas_abi_marketplace/domains/operations/assets/public/support.jpg"`
    - `system_prompt`: prompt template containing `[TOOLS]`
    - `suggestions`: list of dicts with prompt starters:
      - *Feature Request*
      - *Report Bug*

  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> SupportAgent`**
    - Creates and returns a `SupportAgent`.
    - Fetches the default chat model via the workspace model registry.
    - If `agent_configuration` is not provided, builds one by replacing `[TOOLS]` with tool descriptions (currently none).
    - If `agent_shared_state` is not provided, creates `AgentSharedState(thread_id="0")`.
    - Initializes with:
      - `tools=[]`, `agents=[]`, `memory=None`

  - **`onHumanMessage(message: AnyMessage) -> None`**
    - Hook called once per turn when a human message is received (before model inference).
    - Default implementation is a no-op (commented example only).

  - **`onAImessage(message: AnyMessage, agent_name: str) -> None`**
    - Hook called when an AI message is emitted by this agent or its sub-agents.
    - Default implementation is a no-op (commented example only).

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
    - Used by `New()` to obtain the default chat model.
  - `langchain_core.messages.AnyMessage`
    - Type used in message hooks.

- **Configuration behavior**
  - `[TOOLS]` in `system_prompt` is replaced with a bullet list of tools (`- {tool.name}: {tool.description}`).
  - In current code, `tools` is always an empty list, so `[TOOLS]` is replaced with an empty string.

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.SupportAgent import SupportAgent

agent = SupportAgent.New()
print(agent.name)         # Support
print(agent.description)  # Handle support requests: ...
```

## Caveats
- `SupportAgent.New()` asserts the model registry exists:
  - Raises `AssertionError("ModelRegistryService not initialized")` if `get_default_model_registry()` returns `None`.
- Tools and sub-agents are currently hard-coded as empty lists.
- `onHumanMessage` and `onAImessage` are no-ops unless you implement logic inside them.
- Hooks run inline on the streaming thread; slow work should be offloaded (per in-code comments).
