# CommunityManagerAgent

## What it is
- A specialized `Agent` configured as a community management expert (strategy, engagement, social media, events, analytics).
- Provides a pre-defined system prompt and suggestion templates.
- Factory method `New()` wires the agent to the default chat model from the core model registry.

## Public API
- **Class: `CommunityManagerAgent(Agent)`**
  - **Class attributes**
    - `name`: `"CommunityManager"`
    - `description`: Human-readable summary of expertise.
    - `logo_url`: Path to an agent logo asset.
    - `system_prompt`: Base prompt template containing a `[TOOLS]` placeholder.
    - `suggestions`: List of UI/UX suggestion dictionaries (`label`, `value`, `description`).
  - **`@classmethod New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> CommunityManagerAgent`**
    - Creates an instance using:
      - the default chat model from `naas_abi_core.engine.context.get_default_model_registry()`
      - empty `tools` and `agents` lists
      - default `AgentSharedState(thread_id="0")` when not provided
      - default `AgentConfiguration` that injects tool descriptions into `system_prompt` (empty if no tools)
  - **`onHumanMessage(self, message: AnyMessage) -> None`**
    - Hook called when a human message is received. (No implementation in this file.)
  - **`onAImessage(self, message: AnyMessage, agent_name: str) -> None`**
    - Hook called when an AI message is emitted. (No implementation in this file.)

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent` (`Agent`, `AgentConfiguration`, `AgentSharedState`)
  - `naas_abi_core.engine.context.get_default_model_registry()` to obtain a default chat model
  - `langchain_core.messages.AnyMessage` type for message hooks
- Runtime requirement:
  - A default model registry must be initialized; `New()` asserts this:
    - `assert registry is not None, "ModelRegistryService not initialized"`

## Usage
```python
from naas_abi_marketplace.domains.external.agents.CommunityManagerAgent import CommunityManagerAgent

agent = CommunityManagerAgent.New()

# Access metadata/prompts
print(agent.name)
print(agent.description)
```

## Caveats
- `New()` will raise an `AssertionError` if the model registry service is not initialized.
- `tools` are currently always empty in `New()`, so the `[TOOLS]` section in the system prompt will be replaced with an empty string.
- `onHumanMessage` and `onAImessage` are defined but do not perform any actions in this implementation.
