# SoftwareEngineerAgent

## What it is
- A **non-functional template** for a “Software Engineer” domain-expert agent in the `naas_abi_marketplace` ecosystem.
- Defines metadata/constants (name, model, system prompt, suggestions), but **does not create a working agent** yet.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Template factory for the agent.
  - Current behavior: logs a warning and returns `None`.

- `class SoftwareEngineerAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent`.
  - Current behavior: empty (`pass`), no additional methods or overrides.

## Configuration/Dependencies
- Imports:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants (metadata/prompting):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL` (set to `"deepseek-r1"`)
  - `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of UI prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.software-engineer.agents.SoftwareEngineerAgent import create_agent

agent = create_agent()
assert agent is None  # current template behavior
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”**.
- `create_agent()` always returns `None`, and `SoftwareEngineerAgent` contains no implementation.
