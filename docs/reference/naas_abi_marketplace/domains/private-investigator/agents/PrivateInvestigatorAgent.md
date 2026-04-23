# PrivateInvestigatorAgent

## What it is
- A **non-functional template** for a “domain-expert” Private Investigator agent.
- Defines agent metadata/constants (name, model, system prompt, suggestions), but **does not create a working agent**.

## Public API
### `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
- Purpose: Intended factory for creating a Private Investigator agent.
- Current behavior:
  - Logs a warning: `"🚧 PrivateInvestigatorAgent is not functional yet - template only"`.
  - Returns `None`.

### `class PrivateInvestigatorAgent(IntentAgent)`
- Purpose: Placeholder class for a future implementation.
- Current behavior: Empty (`pass`); no additional methods or overrides.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants include (not actively used by code in this file):
  - `MODEL = "gpt-4o"`, `SYSTEM_PROMPT`, `TEMPERATURE = 0`, `DATE = True`, `ONTOLOGY = True`
  - `NAME`, `SLUG`, `TYPE`, `DESCRIPTION`, `AVATAR_URL`
  - `SUGGESTIONS` (prompt examples)

## Usage
```python
from naas_abi_marketplace.domains.private_investigator.agents.PrivateInvestigatorAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not functional
```

## Caveats
- The agent is explicitly marked **“NOT FUNCTIONAL YET”**.
- `create_agent()` always returns `None`; `PrivateInvestigatorAgent` has no implementation.
