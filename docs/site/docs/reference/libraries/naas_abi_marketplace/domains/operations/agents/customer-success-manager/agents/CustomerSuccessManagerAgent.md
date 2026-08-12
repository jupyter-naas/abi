# CustomerSuccessManagerAgent

## What it is
- A **non-functional template** for a “Customer Success Manager” domain-expert agent.
- Defines agent metadata/constants (name, model, system prompt, suggestions), but **does not instantiate a working agent**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended to create and return an agent instance.
  - Current behavior: Logs a warning and returns `None`.

- `class CustomerSuccessManagerAgent(IntentAgent)`
  - Purpose: Placeholder subclass for an intent-based agent.
  - Current behavior: Empty (`pass`); no custom methods or overrides.

## Configuration/Dependencies
- Imports:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration/constants:
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL = "claude-3-5-sonnet"`
  - `SYSTEM_PROMPT` (multi-line role/system instructions)
  - `TEMPERATURE = 0.1`, `DATE = True`, `INSTRUCTIONS_TYPE = "system"`, `ONTOLOGY = True`
  - `SUGGESTIONS` (list of label/value prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.customer-success-manager.agents.CustomerSuccessManagerAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not implemented
```

## Caveats
- **Not functional yet**: `create_agent()` always returns `None`, and `CustomerSuccessManagerAgent` has no implementation.
