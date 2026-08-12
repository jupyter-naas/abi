# ContentCreatorAgent

## What it is
- A specialized `Agent` implementation configured as a content creation expert (copywriting, social media, video scripts, creative campaigns).
- Provides a predefined system prompt and UI-friendly suggestion templates.
- Includes a factory constructor (`New`) that wires in the default chat model from the core model registry.

## Public API

### Class: `ContentCreatorAgent(Agent)`
- **Class attributes**
  - `name: str` — Agent name (`"ContentCreator"`).
  - `description: str` — Human-readable description of the agent’s specialization.
  - `logo_url: str` — Path to a public logo asset.
  - `system_prompt: str` — Role/objective/guidelines/constraints prompt template (includes a `[TOOLS]` placeholder).
  - `suggestions: list[dict]` — Predefined prompt templates (label/value/description) for common content tasks.

- **Class method**
  - `New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> ContentCreatorAgent`
    - Creates and returns a configured `ContentCreatorAgent`.
    - Pulls the default chat model from `naas_abi_core.engine.context.get_default_model_registry()`.
    - If no configuration is provided, injects a tools list into `system_prompt` (tools are currently empty).
    - If no shared state is provided, initializes `AgentSharedState(thread_id="0")`.

- **Instance methods**
  - `onHumanMessage(message: AnyMessage) -> None`
    - Hook called when a user message is received. (No implementation in this file.)
  - `onAImessage(message: AnyMessage, agent_name: str) -> None`
    - Hook called when an AI message is emitted. (No implementation in this file.)

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- Runtime requirement:
  - A default model registry must be initialized; `New()` asserts `registry is not None`.

## Usage
```python
from naas_abi_marketplace.domains.external.agents.ContentCreatorAgent import ContentCreatorAgent

agent = ContentCreatorAgent.New()

# Hooks exist but are no-ops in this implementation:
# agent.onHumanMessage(message)
# agent.onAImessage(message, agent_name="SomeOtherAgent")
```

## Caveats
- `New()` will raise an `AssertionError` if the model registry is not initialized (`"ModelRegistryService not initialized"`).
- No tools are registered in this agent (`tools = []`), so the injected `[TOOLS]` section will be empty.
- The message hooks (`onHumanMessage`, `onAImessage`) are defined but contain no behavior in this file.
