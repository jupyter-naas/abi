# TreasurerAgent

## What it is
- A finance-domain `Agent` implementation configured as a “Treasurer” expert.
- Provides metadata (name/description/logo), a structured `system_prompt`, and UI-style prompt suggestions.
- Factory method `New()` builds an instance using the default chat model from the core model registry.

## Public API
- **Class `TreasurerAgent(Agent)`**
  - **Class attributes**
    - `name`: Display name (`"Treasurer"`).
    - `description`: Short role description.
    - `logo_url`: Path to logo asset.
    - `system_prompt`: Base system prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of suggestion templates (strategy/analysis/optimization/planning).
  - **`@classmethod New(agent_shared_state=None, agent_configuration=None) -> TreasurerAgent`**
    - Creates a `TreasurerAgent` instance.
    - Pulls the default chat model from `naas_abi_core.engine.context.get_default_model_registry()`.
    - If no `AgentConfiguration` is provided:
      - Fills `[TOOLS]` in `system_prompt` using available tools (empty in this implementation).
    - If no `AgentSharedState` is provided:
      - Creates one with `thread_id="0"`.
  - **`onHumanMessage(message: AnyMessage) -> None`**
    - Hook called on each new user message (currently no implementation).
  - **`onAImessage(message: AnyMessage, agent_name: str) -> None`**
    - Hook called on each AI message emission (currently no implementation).

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - A default model registry must be initialized; otherwise `New()` raises an assertion error:
    - `"ModelRegistryService not initialized"`
- **Tools/agents**
  - `tools` and `agents` lists are currently initialized as empty and used only to render the tools section in the prompt.

## Usage
```python
from naas_abi_marketplace.domains.finance.agents.TreasurerAgent import TreasurerAgent

agent = TreasurerAgent.New()

# The instance is ready to be used by the surrounding ABI agent runtime.
print(agent.name)
print(agent.description)
```

## Caveats
- `onHumanMessage` and `onAImessage` are defined but intentionally empty (no side effects).
- `New()` depends on a pre-initialized default model registry; it will fail fast if not available.
- The tools section in the system prompt will be empty because `tools` is an empty list in this file.
