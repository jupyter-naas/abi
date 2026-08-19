# BusinessDevelopmentRepresentativeAgent

## What it is
- A **non-functional template** for a domain-expert “Business Development Representative” agent.
- Defines agent metadata/constants (name, slug, system prompt, suggestions), but **does not create a working agent** yet.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that the agent is not functional yet.
  - **Always returns `None`.**

- `class BusinessDevelopmentRepresentativeAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent`.
  - Contains no methods/implementation (`pass`).

## Configuration/Dependencies
- Imports:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`
- Module-level configuration constants (not wired into a working agent in this file):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`, `MODEL`
  - `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of suggestion templates)

## Usage
```python
from naas_abi_marketplace.domains.business-development-representative.agents.BusinessDevelopmentRepresentativeAgent import create_agent

agent = create_agent()
assert agent is None  # current behavior
```

## Caveats
- Marked **“NOT FUNCTIONAL YET”** in the module docstring and in `create_agent()`.
- `create_agent()` does not instantiate or configure an `IntentAgent`; it only logs a warning and returns `None`.
- `BusinessDevelopmentRepresentativeAgent` is an empty subclass with no behavior.
