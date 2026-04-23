# CommunityManagerAgent

## What it is
- A **non-functional template** for a “Community Manager” domain-expert agent in the `naas_abi_marketplace` project.
- Defines agent metadata (name, description, model, prompts, suggestions) but **does not create a working agent**.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Logs a warning that the agent is not functional and **returns `None`**.
- `class CommunityManagerAgent(IntentAgent)`
  - Placeholder subclass of `IntentAgent` with **no implementation** (`pass`).

## Configuration/Dependencies
- Constants (module-level):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL = "claude-3-5-sonnet"`
  - `SYSTEM_PROMPT` (community-manager expertise and operating guidelines)
  - `TEMPERATURE = 0.3`, `DATE = True`, `INSTRUCTIONS_TYPE = "system"`, `ONTOLOGY = True`
  - `SUGGESTIONS` (preset prompt templates)
- Imports:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`

## Usage
```python
from naas_abi_marketplace.domains.community_manager.agents.CommunityManagerAgent import create_agent

agent = create_agent()
assert agent is None  # template only; no agent instance is created
```

## Caveats
- Marked **“NOT FUNCTIONAL YET”** in docstrings and runtime behavior.
- `create_agent(...)` always returns `None`; `CommunityManagerAgent` has no methods/logic implemented.
