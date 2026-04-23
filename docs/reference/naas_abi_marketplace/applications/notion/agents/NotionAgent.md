# NotionAgent

## What it is
A thin `IntentAgent` wrapper configured as a “Notion” assistant that can **only provide general guidance** about Notion (no tools/actions are configured).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `NotionAgent`.
  - Sets:
    - `name`: `"Notion"`
    - `description`: `"Helps you interact with Notion for workspace and knowledge management."`
    - `system_prompt`: `SYSTEM_PROMPT` (if no configuration provided)
    - `tools`: empty list (no Notion integrations)
    - `intents`: two `IntentType.RAW` intents providing informational responses
    - `memory`: `None`

- `class NotionAgent(IntentAgent)`
  - No additional behavior beyond `IntentAgent` (inherits everything; `pass`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Loads chat model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (`model.model` is passed as `chat_model`)
- Constants:
  - `SYSTEM_PROMPT`: explicitly states no tool access; guidance-only operation
  - `SUGGESTIONS`: empty list

## Usage
```python
from naas_abi_marketplace.applications.notion.agents.NotionAgent import create_agent

agent = create_agent()
# Use `agent` via the surrounding naas_abi framework's execution/runtime interfaces.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot access Notion workspaces, pages, or databases.
- Responses are limited to general information and guidance as described in `SYSTEM_PROMPT`.
