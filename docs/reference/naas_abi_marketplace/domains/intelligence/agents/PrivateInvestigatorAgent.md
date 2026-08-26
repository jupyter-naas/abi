# `PrivateInvestigatorAgent`

## What it is
- A specialized `Agent` implementation for investigation-focused assistance (planning, evidence analysis, surveillance coordination, case documentation).
- Provides a predefined system prompt and UI-oriented suggestion templates.
- Instantiated via a factory-style `New()` classmethod that pulls the default chat model from the workspace model registry.

## Public API

### Class: `PrivateInvestigatorAgent(Agent)`
- **Class attributes**
  - `name: str` — Agent name (`"PrivateInvestigator"`).
  - `description: str` — High-level capability description.
  - `logo_url: str` — Path to the agent logo asset.
  - `system_prompt: str` — Role/objective/guidelines/constraints prompt template (injects tool list into `[TOOLS]`).
  - `suggestions: list[dict]` — Predefined prompt starters:
    - Investigation Plan
    - Evidence Analysis
    - Surveillance Plan
    - Case Report

- **Factory**
  - `@classmethod New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> PrivateInvestigatorAgent`
    - Creates an instance using:
      - Default chat model from `naas_abi_core.engine.context.get_default_model_registry()`.
      - Empty `tools` and empty `agents` lists.
      - `AgentConfiguration` built from `system_prompt` with a rendered tool section when not provided.
      - `AgentSharedState(thread_id="0")` when not provided.

- **Message hooks**
  - `onHumanMessage(self, message: AnyMessage) -> None`
    - Hook called before the user message reaches the model. Default implementation is empty (examples commented out).
  - `onAImessage(self, message: AnyMessage, agent_name: str) -> None`
    - Hook called when an AI message is emitted by this agent or sub-agents (excluding tool-call-only messages). Default implementation is empty (examples commented out).

## Configuration/Dependencies
- **Depends on**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`
  - `langchain_core.messages.AnyMessage`
- **Runtime requirement**
  - A default model registry must be initialized; `New()` asserts `registry is not None`.

## Usage

```python
from naas_abi_marketplace.domains.intelligence.agents.PrivateInvestigatorAgent import (
    PrivateInvestigatorAgent,
)

agent = PrivateInvestigatorAgent.New()

# The agent instance is ready to be used by the surrounding runtime that drives `Agent`.
# (This file defines hooks and construction; message processing is handled by the base `Agent` runtime.)
```

## Caveats
- `New()` will raise an `AssertionError` if the `ModelRegistryService` is not initialized (`registry is None`).
- `tools` and `agents` are empty by default in this implementation; the tool list injected into the prompt will therefore be empty unless modified externally.
- Message hook methods are no-ops unless overridden/implemented.
