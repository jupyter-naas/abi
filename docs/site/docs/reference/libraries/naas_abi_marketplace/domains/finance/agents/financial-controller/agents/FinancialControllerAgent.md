# FinancialControllerAgent

## What it is
- A **non-functional template** for a “Financial Controller” domain-expert agent.
- Defines metadata (name, slug, model, system prompt, suggestions), but **does not create a working agent** yet.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for creating the agent.
  - Current behavior: Logs a warning and returns `None`.
- `class FinancialControllerAgent(IntentAgent)`
  - Purpose: Placeholder subclass for a Financial Controller expert agent.
  - Current behavior: Empty (`pass`), no added methods/overrides.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants (not wired into a working agent in this file):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`, `MODEL`
  - `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.financial-controller.agents.FinancialControllerAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not functional yet
```

## Caveats
- The module explicitly indicates **NOT FUNCTIONAL YET**.
- `create_agent()` always returns `None`, so you cannot instantiate or run a working agent from this file as-is.
