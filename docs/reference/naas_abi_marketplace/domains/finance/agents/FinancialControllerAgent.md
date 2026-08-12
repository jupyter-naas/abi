# FinancialControllerAgent

## What it is
- A specialized `Agent` for financial controlling tasks (planning, budgeting, cost analysis, controls, reporting, variance analysis).
- Provides a pre-defined system prompt and UI-like suggestion templates.
- Instantiated via a `New()` factory that pulls the default chat model from the Naas ABI core model registry.

## Public API
- **Class: `FinancialControllerAgent(Agent)`**
  - **Class attributes**
    - `name`: `"FinancialController"`
    - `description`: High-level purpose of the agent.
    - `logo_url`: Asset path for the agent logo.
    - `system_prompt`: Prompt template (inserts tools list where `[TOOLS]` appears).
    - `suggestions`: List of prompt templates for common tasks.
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> FinancialControllerAgent`**
    - Creates and returns a configured agent instance.
    - Uses the default chat model from `naas_abi_core.engine.context.get_default_model_registry()`.
    - If `agent_configuration` is not provided, builds one from `system_prompt` with a tools section (currently empty).
    - If `agent_shared_state` is not provided, uses `AgentSharedState(thread_id="0")`.
  - **`onHumanMessage(self, message: AnyMessage) -> None`**
    - Hook called when a user message is received. (No implementation in this file.)
  - **`onAImessage(self, message: AnyMessage, agent_name: str) -> None`**
    - Hook called when an AI message is emitted. (No implementation in this file.)

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Model registry requirement**
  - `New()` asserts that the default model registry is initialized:
    - `assert registry is not None, "ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.domains.finance.agents.FinancialControllerAgent import (
    FinancialControllerAgent,
)

agent = FinancialControllerAgent.New()

print(agent.name)
print(agent.description)
print(agent.suggestions[0]["value"])
```

## Caveats
- `New()` will fail if `get_default_model_registry()` returns `None` (model registry not initialized).
- `tools` and `agents` are currently empty in `New()`, so the generated tools section in the prompt will also be empty.
- `onHumanMessage` and `onAImessage` are declared but have no behavior in this file.
