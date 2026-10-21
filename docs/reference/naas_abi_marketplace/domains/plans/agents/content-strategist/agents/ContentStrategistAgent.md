# ContentStrategistAgent

## What it is
A **non-functional template** for a “Content Strategist” domain-expert agent. The module defines metadata/constants and a stubbed factory function; it currently **does not create an operational agent**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that the agent is not functional yet and returns `None`.
- `class ContentStrategistAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent` with no implementation (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants (metadata/template values):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL` (e.g., `"gpt-4o"`)
  - `SYSTEM_PROMPT`
  - `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.content_strategist.agents.ContentStrategistAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not functional
```

## Caveats
- `create_agent()` **always returns `None`** and logs a warning (`"not functional yet - template only"`).
- `ContentStrategistAgent` contains no methods or behavior beyond inheriting from `IntentAgent`.
