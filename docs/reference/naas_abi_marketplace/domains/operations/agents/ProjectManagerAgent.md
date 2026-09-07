# ProjectManagerAgent

## What it is
- An `naas_abi_core` `Agent` implementation configured as a project management specialist (planning, resourcing, risk mitigation, stakeholder communication).
- Provides a predefined `system_prompt` with a `[TOOLS]` placeholder and a set of UI-friendly suggestion templates.
- Includes optional message hooks (`onHumanMessage`, `onAImessage`) for observation/logging (currently no-op).

## Public API

### Class: `ProjectManagerAgent(Agent)`
- **Class attributes**
  - `name: str` — `"ProjectManager"`.
  - `description: str` — persona description.
  - `logo_url: str` — asset path to an agent logo.
  - `system_prompt: str` — XML-like prompt template including a `[TOOLS]` placeholder.
  - `suggestions: list[dict]` — preset prompts:
    - Project Plan
    - Risk Assessment
    - Resource Planning
    - Stakeholder Update

- **Class method**
  - `New(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> ProjectManagerAgent`
    - Factory that:
      - Pulls the workspace default chat model via `get_default_model_registry().get_default_chat_model()`.
      - Creates empty `tools` and `agents` lists.
      - Builds an `AgentConfiguration` from `system_prompt` if not provided (injecting a tools section derived from `tools`).
      - Creates `AgentSharedState(thread_id="0")` if not provided.
      - Instantiates and returns `ProjectManagerAgent` with `memory=None`.

- **Instance methods (hooks)**
  - `onHumanMessage(message: AnyMessage) -> None`
    - Called before the user message reaches the model. No-op by default.
  - `onAImessage(message: AnyMessage, agent_name: str) -> None`
    - Called when an AI message is emitted by this agent or sub-agents (excluding tool-call-only messages). No-op by default.

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - `get_default_model_registry()` must return a non-`None` registry; otherwise `New()` raises an assertion error: `"ModelRegistryService not initialized"`.

## Usage

```python
from naas_abi_marketplace.domains.operations.agents.ProjectManagerAgent import ProjectManagerAgent

agent = ProjectManagerAgent.New()

# Use `agent` wherever a naas_abi_core Agent instance is expected by your runtime.
```

## Caveats
- `New()` asserts the model registry service is initialized; ensure your runtime sets up `get_default_model_registry()`.
- `tools` is initialized as an empty list in `New()`, so the `[TOOLS]` section in the system prompt will be empty unless you provide a custom `AgentConfiguration`.
- Hook methods run inline on the streaming thread (per docstring comments); keep added logic fast to avoid impacting message streaming.
