# AccountantAgent

## What it is
- A finance-domain `Agent` specializing in accounting tasks (financial accounting, bookkeeping, tax preparation support, audit support, compliance).
- Provides a predefined system prompt and suggestion templates, and a factory method to instantiate the agent with the platform’s default chat model.

## Public API
- `class AccountantAgent(Agent)`
  - Class attributes:
    - `name: str` — Agent display name (`"Accountant"`).
    - `description: str` — Brief capability description.
    - `logo_url: str` — Path to agent logo asset.
    - `system_prompt: str` — Base prompt template (includes a `[TOOLS]` placeholder).
    - `suggestions: list[dict]` — UI/UX prompt suggestions (label/value/description).
  - `@classmethod New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> AccountantAgent`
    - Creates an `AccountantAgent` using the default chat model from the default model registry.
    - If no `agent_configuration` is provided, it builds one by injecting the current tool list into `system_prompt` (tools list is empty in this implementation).
    - If no `agent_shared_state` is provided, initializes `AgentSharedState(thread_id="0")`.
  - `onHumanMessage(self, message: AnyMessage) -> None`
    - Hook called when the user sends a message (no implementation in this file).
  - `onAImessage(self, message: AnyMessage, agent_name: str) -> None`
    - Hook called when an AI message is emitted (no implementation in this file).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- Runtime requirement:
  - A default model registry must be initialized; otherwise `New()` asserts with:
    - `"ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.domains.finance.agents.AccountantAgent import AccountantAgent

agent = AccountantAgent.New()

print(agent.name)
print(agent.description)
```

## Caveats
- `New()` uses an assertion to require the default model registry to be initialized.
- The `tools` and `agents` lists are empty in this implementation; the `[TOOLS]` section will be blank unless the code is extended.
- `onHumanMessage` and `onAImessage` are defined but contain no behavior here.
