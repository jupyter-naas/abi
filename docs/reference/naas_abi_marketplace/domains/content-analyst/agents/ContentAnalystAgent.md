# ContentAnalystAgent

## What it is
A **non-functional template** for a “Content Analyst” domain-expert agent in the `naas_abi_marketplace` package. The module defines metadata (name, slug, model, prompt, etc.) but does **not** construct a working agent yet.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that the agent is not functional and returns `None`.
- `class ContentAnalystAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent` with no implementation (`pass`).

## Configuration/Dependencies
- **Depends on**:
  - `naas_abi_core.logger` (used to emit a warning)
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- **Module-level configuration constants** (currently unused by `create_agent`):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL`, `SYSTEM_PROMPT`, `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (list of label/value prompt templates)

## Usage
```python
from naas_abi_marketplace.domains.content-analyst.agents.ContentAnalystAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not functional yet
```

## Caveats
- `create_agent()` **always returns `None`** and only logs a warning.
- `ContentAnalystAgent` contains **no implemented behavior** beyond inheriting from `IntentAgent`.
