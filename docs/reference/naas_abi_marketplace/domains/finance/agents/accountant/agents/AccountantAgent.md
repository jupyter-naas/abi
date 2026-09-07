# AccountantAgent

## What it is
- A **non-functional template** for a domain-expert “Accountant” agent.
- Defines metadata/constants (name, prompt, suggestions) but does **not** instantiate a working agent.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that this agent is not functional yet.
  - Always returns `None`.

- `class AccountantAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent`.
  - Contains no implementation (`pass`).

## Configuration/Dependencies
- Imports from `naas_abi_core`:
  - `logger`
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState` from `naas_abi_core.services.agent.IntentAgent`
- Module-level constants (currently unused by `create_agent`):
  - Identity/metadata: `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - Model/prompting: `MODEL`, `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - UI hints: `SUGGESTIONS`

## Usage
```python
from naas_abi_marketplace.domains.accountant.agents.AccountantAgent import create_agent

agent = create_agent()
assert agent is None  # template only
```

## Caveats
- The module explicitly states **“NOT FUNCTIONAL YET”**.
- `create_agent()` does not create or return an `IntentAgent` instance.
- `AccountantAgent` has no behavior implemented.
