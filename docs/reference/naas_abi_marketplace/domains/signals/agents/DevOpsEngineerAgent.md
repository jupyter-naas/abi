# DevOpsEngineerAgent

## What it is
- A specialized `Agent` implementation representing a DevOps engineer persona.
- Provides preset metadata (`name`, `description`, `logo_url`), a structured `system_prompt`, and a list of UI-style `suggestions`.
- Includes a `New()` factory that builds the agent using the default chat model from the core model registry.

## Public API
- **Class `DevOpsEngineerAgent(Agent)`**
  - **Class attributes**
    - `name`: `"DevOpsEngineer"`
    - `description`: DevOps-focused description string.
    - `logo_url`: Asset path for the agent image.
    - `system_prompt`: Prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of dictionaries with:
      - `label`: short title
      - `value`: templated prompt
      - `description`: short explanation
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> DevOpsEngineerAgent`**
    - Creates an instance with:
      - `chat_model` from `get_default_model_registry().get_default_chat_model()`
      - empty `tools` and `agents` lists
      - default `AgentSharedState(thread_id="0")` if none provided
      - default `AgentConfiguration` if none provided, with `[TOOLS]` replaced by a bullet list (empty here because tools are empty)
  - **`onHumanMessage(message: AnyMessage) -> None`**
    - Hook invoked when the user sends a message (no implementation in this file).
  - **`onAImessage(message: AnyMessage, agent_name: str) -> None`**
    - Hook invoked when an AI message is emitted (no implementation in this file).

## Configuration/Dependencies
- **Imports/Dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - A default model registry must be available; `New()` asserts this with: `"ModelRegistryService not initialized"`.

## Usage
```python
from naas_abi_marketplace.domains.signals.agents.DevOpsEngineerAgent import DevOpsEngineerAgent

agent = DevOpsEngineerAgent.New()

print(agent.name)
print(agent.description)
```

## Caveats
- `New()` will fail if the default model registry is not initialized (assertion error).
- `tools` are hard-coded as empty in this file; the `[TOOLS]` section in the system prompt will be empty unless a custom `AgentConfiguration` is provided.
- `onHumanMessage` and `onAImessage` are defined as hooks but have no behavior here.
