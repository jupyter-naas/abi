# SoftwareEngineerAgent

## What it is
- A specialized `Agent` configured to behave as a software engineering expert.
- Provides static metadata (name/description/logo), a predefined `system_prompt`, and suggestion templates.
- Instantiated via `New()` using the default chat model from the core model registry.

## Public API
- **Class: `SoftwareEngineerAgent(Agent)`**
  - **Class attributes**
    - `name`: `"SoftwareEngineer"`
    - `description`: Software engineering expertise summary.
    - `logo_url`: Asset path to the agent logo.
    - `system_prompt`: Prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of dict templates (code review, architecture, debugging, testing).
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> SoftwareEngineerAgent`**
    - Creates a configured `SoftwareEngineerAgent`.
    - Fetches the default chat model from `naas_abi_core.engine.context.get_default_model_registry()`.
    - If `agent_configuration` is not provided, fills `[TOOLS]` with a generated tools section (empty in this implementation).
    - Defaults `agent_shared_state` to `AgentSharedState(thread_id="0")` when not provided.
  - **`onHumanMessage(message: AnyMessage) -> None`**
    - Hook called when a human/user message is received (no implementation).
  - **`onAImessage(message: AnyMessage, agent_name: str) -> None`**
    - Hook called when an AI message is emitted (no implementation).

## Configuration/Dependencies
- **Dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - `New()` asserts the default model registry exists:
    - `assert registry is not None, "ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.domains.signals.agents.SoftwareEngineerAgent import SoftwareEngineerAgent

agent = SoftwareEngineerAgent.New()
print(agent.name)  # SoftwareEngineer
```

## Caveats
- `New()` raises an `AssertionError` if `ModelRegistryService` is not initialized.
- `tools` and `agents` are instantiated as empty lists here; the `[TOOLS]` section will be empty unless the code is extended to add tools.
- `onHumanMessage` and `onAImessage` are defined as hooks but contain no logic in this file.
