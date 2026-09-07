# SalesDevelopmentRepresentativeAgent

## What it is
- A preconfigured `Agent` specialized for sales development workflows:
  - lead generation, prospecting, qualification (BANT/MEDDIC), outreach, and pipeline management.
- Provides a built-in `system_prompt` template (with a `[TOOLS]` placeholder) and task suggestions.
- Constructed via a `New()` factory that pulls the workspace default chat model from the default model registry.

## Public API
- **Class: `SalesDevelopmentRepresentativeAgent(Agent)`**
  - **Class attributes**
    - `name`: `"SalesDevelopmentRepresentative"`
    - `description`: Sales development specialization summary
    - `logo_url`: Asset path to the agent logo
    - `system_prompt`: Prompt template with `[TOOLS]` placeholder
    - `suggestions`: List of dictionaries (`label`, `value`, `description`) for common tasks
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> SalesDevelopmentRepresentativeAgent`**
    - Creates an instance using:
      - `get_default_model_registry().get_default_chat_model()` for `chat_model`
      - `tools=[]` and `agents=[]`
      - `AgentConfiguration(system_prompt=...)` built from `system_prompt` with `[TOOLS]` replaced by tool descriptions (empty by default)
      - `AgentSharedState(thread_id="0")` if no shared state is provided
  - **Message hooks (no-op by default)**
    - `onHumanMessage(message: AnyMessage) -> None`: called once per user turn, before the message reaches the model.
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`: called when an AI message is emitted by this agent or any sub-agent (tool-call-only messages are not reported).

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage` (hook method type)
- **Runtime requirement**
  - The default model registry must be initialized; `New()` asserts it is not `None`.

## Usage
```python
from naas_abi_marketplace.domains.operations.agents.SalesDevelopmentRepresentativeAgent import (
    SalesDevelopmentRepresentativeAgent,
)

agent = SalesDevelopmentRepresentativeAgent.New()
```

## Caveats
- `New()` raises an `AssertionError` if the default model registry is not initialized (`"ModelRegistryService not initialized"`).
- No tools or sub-agents are registered by default (`tools=[]`, `agents=[]`), so the `[TOOLS]` section in the system prompt will be empty unless you pass a custom `AgentConfiguration`.
