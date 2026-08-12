# OSINTResearcherAgent

## What it is
- A **non-functional template** for an OSINT (Open Source Intelligence) domain expert agent.
- Defines constants (metadata, prompts, suggestions) but **does not create a working agent**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for an OSINT Researcher agent.
  - Current behavior: Logs a warning and returns `None`.

- `class OSINTResearcherAgent(IntentAgent)`
  - Purpose: Placeholder class for a future OSINT Researcher agent implementation.
  - Current behavior: Empty (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants (not actively used by code here, but defined):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL` (set to `"gpt-4o"`)
  - `SYSTEM_PROMPT`
  - `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of suggested prompts)

## Usage
```python
from naas_abi_marketplace.domains.osint_researcher.agents.OSINTResearcherAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not implemented
```

## Caveats
- The module explicitly states it is **“NOT FUNCTIONAL YET”**.
- `create_agent()` always returns `None`; `OSINTResearcherAgent` has no implementation.
