# SharePointAgent

## What it is
A minimal `IntentAgent` implementation for SharePoint guidance. It provides general informational responses about SharePoint features and document/site management, but **does not include any SharePoint tools** for real operations.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `SharePointAgent`.
  - Sets:
    - `name`: `"SharePoint"`
    - `description`: SharePoint document management/collaboration helper
    - `system_prompt`: guidance-only (no tool access)
    - `tools`: empty list
    - `intents`: two predefined RAW intents (features; document/site management)
    - `state`: provided or new `AgentSharedState`
    - `configuration`: provided or new `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
    - `memory`: `None`

- `class SharePointAgent(IntentAgent)`
  - Concrete agent type (no additional methods; inherits behavior from `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Uses chat model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` (passed as `chat_model=model.model`)
- No tools are configured (`tools = []`).
- Key module constants:
  - `NAME`, `DESCRIPTION`, `SYSTEM_PROMPT`, `SUGGESTIONS` (empty list)

## Usage
```python
from naas_abi_marketplace.applications.sharepoint.agents.SharePointAgent import create_agent

agent = create_agent()
# Use agent via the IntentAgent interface provided by naas_abi_core
```

## Caveats
- This agent **cannot access SharePoint** or perform document/site actions because **no tools are provided**.
- Responses are limited to general guidance based on the system prompt and predefined intents.
