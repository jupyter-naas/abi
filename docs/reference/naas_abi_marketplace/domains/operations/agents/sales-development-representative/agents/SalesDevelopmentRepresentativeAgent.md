# SalesDevelopmentRepresentativeAgent

## What it is
- A **non-functional template** for a “Sales Development Representative” domain-expert agent.
- Defines metadata/constants (name, model, system prompt, suggestions) but does **not** implement agent creation or behavior.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for creating the agent.
  - Current behavior: Logs a warning and returns `None`.

- `class SalesDevelopmentRepresentativeAgent(IntentAgent)`
  - Purpose: Placeholder class for an SDR expert agent.
  - Current behavior: No implementation (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants (not actively used by code here):
  - `MODEL = "gpt-4o"`, `TEMPERATURE = 0.2`
  - `SYSTEM_PROMPT` (SDR-focused instructions)
  - `SUGGESTIONS` (predefined prompt starters)
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`

## Usage
```python
from naas_abi_marketplace.domains.sales-development-representative.agents.SalesDevelopmentRepresentativeAgent import create_agent

agent = create_agent()
assert agent is None  # current template behavior
```

## Caveats
- Marked **“NOT FUNCTIONAL YET”**:
  - `create_agent()` always returns `None`.
  - `SalesDevelopmentRepresentativeAgent` has no implemented methods/logic.
