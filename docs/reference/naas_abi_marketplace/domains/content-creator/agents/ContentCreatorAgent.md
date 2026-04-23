# ContentCreatorAgent

## What it is
- A **non-functional template** for a “Content Creator” domain-expert agent in the `naas_abi_marketplace` project.
- Defines agent metadata (name, slug, model, prompt, suggestions), but **does not create a working agent** yet.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[IntentAgent]`
  - Purpose: Intended factory for creating an agent instance.
  - Current behavior: Logs a warning and returns `None`.

- `class ContentCreatorAgent(IntentAgent)`
  - Purpose: Placeholder class for a future implementation.
  - Current behavior: Empty (`pass`).

## Configuration/Dependencies
- Depends on `naas_abi_core`:
  - `naas_abi_core.logger`
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`
    - `AgentConfiguration`
    - `AgentSharedState`
- Module-level constants (metadata/config):
  - `AVATAR_URL`, `NAME`, `TYPE`, `SLUG`, `DESCRIPTION`
  - `MODEL` (set to `"claude-3-5-sonnet"`)
  - `SYSTEM_PROMPT` (content creation expert prompt)
  - `TEMPERATURE`, `DATE`, `INSTRUCTIONS_TYPE`, `ONTOLOGY`
  - `SUGGESTIONS` (UI/action prompt suggestions)

## Usage
```python
from naas_abi_marketplace.domains.content_creator.agents.ContentCreatorAgent import create_agent

agent = create_agent()
assert agent is None  # current implementation returns None
```

## Caveats
- The module is explicitly marked **“NOT FUNCTIONAL YET”**.
- `create_agent(...)` **always returns `None`** and only emits a warning.
- `ContentCreatorAgent` has no implemented behavior beyond inheriting `IntentAgent`.
