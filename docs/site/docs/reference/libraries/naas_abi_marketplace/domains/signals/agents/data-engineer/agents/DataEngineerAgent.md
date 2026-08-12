# DataEngineerAgent

## What it is
- A **non-functional template** for a “Data Engineer” domain-expert agent.
- Defines metadata/constants (name, model, system prompt, suggestions) but **does not create a working agent**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for creating the agent.
  - Current behavior: Logs a warning and returns `None`.

- `class DataEngineerAgent(IntentAgent)`
  - Purpose: Placeholder class for a future implementation.
  - Current behavior: Empty (`pass`); no additional methods/overrides.

## Configuration/Dependencies
- Imports:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level constants (metadata/templates):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`, `MODEL`
  - `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of UI prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.data_engineer.agents.DataEngineerAgent import create_agent

agent = create_agent()
assert agent is None  # current implementation
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”**.
- `create_agent()` always returns `None`; `DataEngineerAgent` has no behavior implemented.
