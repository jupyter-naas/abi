# ProjectManagerAgent

## What it is
A **non-functional template** for a “Project Manager” domain-expert agent in the `naas_abi_marketplace` project. The module defines metadata/constants and a stubbed factory and agent class.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended to create and return a configured Project Manager agent.
  - Current behavior: Logs a warning and returns `None`.

- `class ProjectManagerAgent(IntentAgent)`
  - Purpose: Placeholder class for a Project Manager expert agent.
  - Current behavior: Empty (`pass`); no additional methods or overrides.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration/constants (currently unused by code in this file but defined):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`, `MODEL`
  - `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.project_manager.agents.ProjectManagerAgent import create_agent

agent = create_agent()
assert agent is None  # template: always returns None
```

## Caveats
- Explicitly marked **“NOT FUNCTIONAL YET”**.
- `create_agent()` always returns `None`; `ProjectManagerAgent` has no implementation.
