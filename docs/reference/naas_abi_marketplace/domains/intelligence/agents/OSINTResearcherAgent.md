# OSINTResearcherAgent

## What it is
- `OSINTResearcherAgent` is an `Agent` specialization configured as an OSINT (Open Source Intelligence) research assistant.
- It defines static metadata (name, description, logo), a detailed `system_prompt`, and a set of UI-style prompt `suggestions`.
- It provides a `New()` factory for constructing an instance using the workspace’s default chat model.

## Public API
- **Class `OSINTResearcherAgent(Agent)`**
  - **Class attributes**
    - `name: str` — Agent name (`"OSINTResearcher"`).
    - `description: str` — High-level description of OSINT expertise.
    - `logo_url: str` — Path to an agent logo asset.
    - `system_prompt: str` — Prompt template containing `[TOOLS]` placeholder.
    - `suggestions: list[dict]` — Predefined prompt templates (gathering, threat analysis, investigation, reporting).
  - **`@classmethod New(cls, agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> OSINTResearcherAgent`**
    - Creates an agent instance:
      - Fetches the default chat model from the default model registry.
      - Uses empty `tools` and empty `agents` lists.
      - Builds an `AgentConfiguration` from `system_prompt` if none provided (replacing `[TOOLS]` with a generated list; currently empty).
      - Creates a default `AgentSharedState(thread_id="0")` if none provided.
  - **Message hooks**
    - `onHumanMessage(self, message: AnyMessage) -> None`
      - Hook invoked when a user message is received (before model call). Body is currently a no-op (example logging commented out).
    - `onAImessage(self, message: AnyMessage, agent_name: str) -> None`
      - Hook invoked when an AI message is emitted (from this agent or sub-agents). Body is currently a no-op (example logging commented out).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent`:
    - `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `naas_abi_core.engine.context.get_default_model_registry`:
    - Must be initialized; `New()` asserts registry is not `None`.
  - `langchain_core.messages.AnyMessage` for hook signatures.
- `New()` currently configures:
  - `tools = []`
  - `agents = []`
  - `memory = None`

## Usage
```python
from naas_abi_marketplace.domains.intelligence.agents.OSINTResearcherAgent import (
    OSINTResearcherAgent,
)

agent = OSINTResearcherAgent.New()

# Hooks exist but do nothing by default unless you override/extend the class.
```

## Caveats
- `OSINTResearcherAgent.New()` will raise an `AssertionError` if the default model registry is not initialized (`ModelRegistryService not initialized`).
- The `[TOOLS]` section in the system prompt is populated from `tools`, but `tools` is currently an empty list in this implementation.
