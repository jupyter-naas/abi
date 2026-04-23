# GoogleDriveAgent

## What it is
A minimal `IntentAgent` wrapper configured to provide **general guidance** about Google Drive (features, file/folder management). It defines **no tools**, so it cannot access or modify Google Drive—only respond with informational guidance.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `GoogleDriveAgent`.
  - Sets:
    - `name`: `"Google_Drive"`
    - `description`: guidance-focused description
    - `system_prompt`: guidance-only constraints
    - `tools`: `[]` (none)
    - `intents`: two RAW intents providing canned guidance responses
    - `state`: provided or new `AgentSharedState()`
    - `configuration`: provided or `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`
    - `chat_model`: imported from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`

- `class GoogleDriveAgent(IntentAgent)`
  - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses chat model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (imports `model`, uses `model.model`)
- Key module constants:
  - `SYSTEM_PROMPT`: explicitly states *no access to Google Drive tools* and restricts actions to general guidance.
  - `SUGGESTIONS`: empty list.

## Usage
```python
from naas_abi_marketplace.applications.google_drive.agents.GoogleDriveAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent (GoogleDriveAgent) configured with no tools.
print(agent.name)         # "Google_Drive"
print(agent.description)  # Helps you interact with Google Drive...
```

## Caveats
- No tools are configured (`tools = []`), so the agent **cannot** list/upload/download/manage real Drive files; it can only provide general information and guidance as defined in `SYSTEM_PROMPT`.
