# CampaignManagerAgent

## What it is
A **non-functional template** for a “Campaign Manager” domain-expert agent intended to provide marketing campaign strategy and optimization guidance. The module currently only defines metadata/constants and a stubbed factory that returns `None`.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended to create and return an `IntentAgent` instance for the Campaign Manager domain.
  - Current behavior: Logs a warning and **returns `None`**.

- `class CampaignManagerAgent(IntentAgent)`
  - Purpose: Placeholder subclass of `IntentAgent`.
  - Current behavior: Empty (`pass`), **no additional methods or overrides**.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`

- Module-level metadata/constants (currently unused by the stub implementation):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL`, `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.campaign-manager.agents.CampaignManagerAgent import create_agent

agent = create_agent()
assert agent is None  # current implementation
```

## Caveats
- Marked as **“NOT FUNCTIONAL YET - template only”**.
- `create_agent(...)` always returns `None`; `CampaignManagerAgent` has no implementation.
