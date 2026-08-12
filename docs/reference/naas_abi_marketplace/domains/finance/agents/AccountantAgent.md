# AccountantAgent

## What it is
- A finance-domain `Agent` specialization configured as an expert accountant.
- Provides a predefined system prompt, metadata (name/description/logo), and suggested user actions.
- Includes a factory constructor (`New`) that wires the agent to the default chat model from the Naas ABI core model registry.

## Public API
- `class AccountantAgent(Agent)`
  - **Class attributes**
    - `name`: `"Accountant"`
    - `description`: Expert accountant scope (GAAP/IFRS, bookkeeping, tax prep, audit support, compliance)
    - `logo_url`: Path to an accountant image asset
    - `system_prompt`: Role/objective/guidelines/constraints prompt template (tools list injected at creation)
    - `suggestions`: List of suggestion dicts (label/value/description)
  - **Constructors**
    - `@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> AccountantAgent`
      - Creates an instance using:
        - Default chat model from `naas_abi_core.engine.context.get_default_model_registry()`
        - Empty `tools` and `agents` lists
        - `AgentConfiguration` with `[TOOLS]` placeholder replaced by a generated tools section (empty by default)
        - Default `AgentSharedState(thread_id="0")` if not provided
  - **Hooks / callbacks**
    - `onHumanMessage(message: AnyMessage) -> None`
      - Called when the user sends a new message (no implementation in this file).
    - `onAImessage(message: AnyMessage, agent_name: str) -> None`
      - Called when an AI message is emitted (no implementation in this file).

## Configuration/Dependencies
- Depends on Naas ABI core:
  - `naas_abi_core.services.agent.Agent` (`Agent`, `AgentConfiguration`, `AgentSharedState`)
  - `naas_abi_core.engine.context.get_default_model_registry`
- Depends on LangChain message types:
  - `langchain_core.messages.AnyMessage`
- Runtime requirement:
  - A default model registry must be initialized; otherwise `New()` raises via:
    - `assert registry is not None, "ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.domains.finance.agents.AccountantAgent import AccountantAgent

agent = AccountantAgent.New()
print(agent.name)  # "Accountant"
```

## Caveats
- `New()` requires the Naas ABI `ModelRegistryService` to be initialized (assertion failure otherwise).
- `tools` and `agents` are empty in this implementation; the injected `[TOOLS]` section will be blank unless tools are added elsewhere.
- `onHumanMessage` / `onAImessage` are defined but contain no logic in this file.
