# DevOpsEngineerAgent

## What it is
- A **non-functional template** for a “DevOps Engineer” domain-expert agent.
- Defines metadata/constants (name, prompt, model, suggestions) but **does not create a working agent** yet.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for creating the agent.
  - Current behavior: Logs a warning and **returns `None`**.
- `class DevOpsEngineerAgent(IntentAgent)`
  - Purpose: Placeholder class for a DevOps Engineer expert agent.
  - Current behavior: Empty (`pass`), **no additional methods/overrides**.

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level configuration constants:
  - `MODEL = "deepseek-r1"`, `SYSTEM_PROMPT`, `TEMPERATURE = 0`, `DATE = True`, `INSTRUCTIONS_TYPE = "system"`, `ONTOLOGY = True`
  - Presentation/metadata: `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `SUGGESTIONS`: predefined prompt templates for common DevOps tasks

## Usage
```python
from naas_abi_marketplace.domains.devops_engineer.agents.DevOpsEngineerAgent import create_agent

agent = create_agent()
assert agent is None  # template only; not functional yet
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”**.
- `create_agent()` **always returns `None`** and only emits a warning.
- `DevOpsEngineerAgent` contains **no implementation** beyond inheriting `IntentAgent`.
