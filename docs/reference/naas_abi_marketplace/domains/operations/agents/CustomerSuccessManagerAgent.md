# CustomerSuccessManagerAgent

## What it is
- An `Agent` implementation representing a Customer Success Manager persona.
- Provides:
  - Predefined system prompt (with a `[TOOLS]` placeholder).
  - Agent metadata (name/description/logo).
  - Suggestion templates for common customer success tasks.
- Includes a factory (`New`) that wires the agent to the workspace default chat model via the model registry.

## Public API

### Class: `CustomerSuccessManagerAgent(Agent)`
- **Class attributes**
  - `name`: `"CustomerSuccessManager"`
  - `description`: Customer success specialization summary.
  - `logo_url`: Asset path to an image.
  - `system_prompt`: Prompt template including `<tools>[TOOLS]</tools>`.
  - `suggestions`: List of dicts with:
    - `label`
    - `value` (templated text)
    - `description`

- **Class method**
  - `New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> CustomerSuccessManagerAgent`
    - Creates and returns a configured agent instance.
    - Pulls the default chat model from `naas_abi_core.engine.context.get_default_model_registry()`.
    - If `agent_configuration` is not provided, builds one from `system_prompt` by replacing `[TOOLS]` with a formatted tool list (empty in this file).
    - If `agent_shared_state` is not provided, defaults to `AgentSharedState(thread_id="0")`.
    - Configures:
      - `tools = []`
      - `agents = []`
      - `memory = None`

- **Message hooks**
  - `onHumanMessage(message: AnyMessage) -> None`
    - Called once per user turn, before the message reaches the model.
    - No-op (example logging is commented out).
  - `onAImessage(message: AnyMessage, agent_name: str) -> None`
    - Called when an AI message is emitted by this agent or sub-agents (excluding tool-call-only messages).
    - No-op (example logging is commented out).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry()`: must be initialized
  - `langchain_core.messages.AnyMessage` (typing for hooks)
- Runtime requirement:
  - A default model registry must exist; otherwise `New()` raises an `AssertionError` with `"ModelRegistryService not initialized"`.

## Usage

```python
from naas_abi_marketplace.domains.operations.agents.CustomerSuccessManagerAgent import (
    CustomerSuccessManagerAgent,
)

agent = CustomerSuccessManagerAgent.New()

print(agent.name)
print(agent.description)
print(agent.configuration.system_prompt)
print(agent.suggestions)
```

## Caveats
- `CustomerSuccessManagerAgent.New()` asserts if the model registry is not initialized.
- This implementation configures no tools and no sub-agents (`tools=[]`, `agents=[]`), so the `[TOOLS]` prompt section will be empty unless you pass a custom `AgentConfiguration`.
- Message hooks are present but do nothing unless you implement their bodies.
