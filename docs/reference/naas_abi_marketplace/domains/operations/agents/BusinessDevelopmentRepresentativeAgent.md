# BusinessDevelopmentRepresentativeAgent

## What it is
- A domain-specific `Agent` implementation configured as a Business Development Representative.
- Provides predefined metadata (name/description/logo), a BD-focused `system_prompt`, and UI-style prompt `suggestions`.
- Instantiated via a `New()` factory that uses the workspace default chat model from the Naas ABI model registry.

## Public API
- `class BusinessDevelopmentRepresentativeAgent(Agent)`
  - **Static attributes**
    - `name`: `"BusinessDevelopmentRepresentative"`
    - `description`: Business development/partnerships-focused description string
    - `logo_url`: Path to the agent logo asset
    - `system_prompt`: Prompt template containing a `[TOOLS]` placeholder
    - `suggestions`: List of dictionaries with:
      - `label`, `value`, `description` (common BD tasks)
  - **Factory**
    - `@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> BusinessDevelopmentRepresentativeAgent`
      - Retrieves the default chat model via `get_default_model_registry().get_default_chat_model()`
      - Initializes with:
        - `tools`: empty list
        - `agents`: empty list
        - `memory`: `None`
      - If `agent_configuration` is not provided:
        - Replaces `[TOOLS]` in `system_prompt` with a generated tools section (empty with current defaults)
      - If `agent_shared_state` is not provided:
        - Uses `AgentSharedState(thread_id="0")`
  - **Message hooks** (observation points; no-op by default)
    - `onHumanMessage(message: AnyMessage) -> None`
      - Called before the user message reaches the model
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`
      - Called when an AI message is emitted (from this agent or sub-agents)

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`:
    - Used to obtain the default chat model
  - `langchain_core.messages.AnyMessage`:
    - Used in message hook signatures
- **Default configuration behavior**
  - Tools list is empty, so the `[TOOLS]` section becomes an empty string.
  - Shared state defaults to `AgentSharedState(thread_id="0")`.

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.BusinessDevelopmentRepresentativeAgent import (
    BusinessDevelopmentRepresentativeAgent,
)

agent = BusinessDevelopmentRepresentativeAgent.New()

# Optional: override hooks in a subclass or edit method bodies to add logging/metrics.
```

## Caveats
- `New()` asserts the model registry is initialized:
  - If `get_default_model_registry()` returns `None`, it raises `AssertionError("ModelRegistryService not initialized")`.
- No tools or sub-agents are configured in `New()` (`tools = []`, `agents = []`).
- Hook methods run inline on the streaming thread; keep any added logic fast.
