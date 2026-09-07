# AccountExecutiveAgent

## What it is
A **non-functional template** for an “Account Executive” domain-expert agent. The module defines metadata (name, model, system prompt, suggestions) but does **not** currently create a working agent instance.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Template factory function.
  - Logs a warning and **always returns `None`**.

- `class AccountExecutiveAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent`.
  - Contains no implementation (`pass`).

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level metadata/constants (not wired to runtime behavior in this file):
  - `MODEL = "gpt-4o"`
  - `SYSTEM_PROMPT` (account executive expertise and operating guidelines)
  - `TEMPERATURE = 0.2`, `DATE = True`, `ONTOLOGY = True`, `INSTRUCTIONS_TYPE = "system"`
  - `SUGGESTIONS` (prompt templates)
  - `NAME`, `SLUG`, `TYPE`, `DESCRIPTION`, `AVATAR_URL`

## Usage
```python
from naas_abi_marketplace.domains.account-executive.agents.AccountExecutiveAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not functional
```

## Caveats
- `create_agent(...)` logs a warning and returns `None`; no agent instance is created.
- `AccountExecutiveAgent` has no behavior beyond its base class and is not instantiated here.
