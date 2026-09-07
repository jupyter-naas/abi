# TreasurerAgent

## What it is
- A **non-functional template** for a “Treasurer” domain-expert agent (cash management, risk assessment, investment strategy, treasury operations).
- Includes metadata constants (name, model, system prompt, suggestions), but does **not** implement a working agent.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for creating the Treasurer agent.
  - Current behavior: Logs a warning and returns `None`.

- `class TreasurerAgent(IntentAgent)`
  - Purpose: Placeholder class for a Treasurer expert agent.
  - Current behavior: Empty (`pass`), no additional methods or overrides.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants:
  - `MODEL = "gpt-4o"`, `TEMPERATURE = 0`, `SYSTEM_PROMPT` (treasurer expertise), `SUGGESTIONS` (prompt templates), etc.

## Usage
```python
from naas_abi_marketplace.domains.treasurer.agents.TreasurerAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not implemented yet
```

## Caveats
- Marked explicitly as **“NOT FUNCTIONAL YET - template only”**.
- `create_agent()` always returns `None`; `TreasurerAgent` contains no implementation.
