# HumanResourcesAgent

## What it is
- A **non-functional template** for a Human Resources “domain-expert” agent.
- Defines metadata/constants (name, model, system prompt, suggestions) but **does not create a working agent**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that this agent is not functional and **returns `None`**.
- `class HumanResourcesAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent` with **no implementation**.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level constants (metadata):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`, `MODEL`
  - `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.human-resources-manager.agents.HumanResourcesAgent import create_agent

agent = create_agent()
assert agent is None  # template only; no functional agent is created
```

## Caveats
- Marked **“NOT FUNCTIONAL YET”** in the module docstring and in `create_agent`.
- `create_agent` always returns `None`.
- `HumanResourcesAgent` contains no behavior (`pass`).
