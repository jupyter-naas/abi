# NotionAgent

## What it is
An `IntentAgent` specialization configured as a Notion-focused assistant that **provides general guidance only** (no Notion tools/integrations are configured).

## Public API
- `class NotionAgent(IntentAgent)`
  - Preconfigured attributes:
    - `name = "Notion"`
    - `description = "Helps you interact with Notion for workspace and knowledge management."`
    - `system_prompt`: guidance-only prompt explicitly stating no tool access
    - `suggestions = []`
  - `@classmethod New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> NotionAgent`
    - Factory that builds a configured `NotionAgent`.
    - Loads default chat and embedding models from the module engine’s model registry.
    - Sets:
      - `tools`: `[]`
      - `intents`: two `IntentType.RAW` intents with static informational targets
      - `memory`: `None`
    - Defaults:
      - `agent_configuration`: `AgentConfiguration(system_prompt=cls.system_prompt)`
      - `agent_shared_state`: `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on `naas_abi_marketplace.applications.notion.ABIModule`:
  - Used to access `abi_module.engine.services.model_registry`
  - Requires model registry service to be initialized (asserts non-`None`)
- Model retrieval:
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.notion.agents.NotionAgent import NotionAgent

agent = NotionAgent.New()
# Use `agent` through the surrounding naas_abi runtime/execution framework.
```

## Caveats
- No tools are configured (`tools = []`), so it cannot access or modify Notion workspaces/pages/databases.
- Requires a initialized ModelRegistryService; otherwise `New()` raises an assertion error.
