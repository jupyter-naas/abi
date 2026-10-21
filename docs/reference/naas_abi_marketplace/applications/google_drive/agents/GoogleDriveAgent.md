# GoogleDriveAgent

## What it is
An `IntentAgent` specialization that provides **general guidance** about Google Drive (features, file/folder management, storage best practices). It is configured with **no tools**, so it cannot access or modify real Google Drive content.

## Public API
- `class GoogleDriveAgent(IntentAgent)`
  - Agent class with predefined:
    - `name = "Google_Drive"`
    - `description`
    - `system_prompt` (explicitly states no tool access; guidance only)
    - `suggestions = []`

- `GoogleDriveAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GoogleDriveAgent`
  - Factory constructor that:
    - Retrieves default chat and embedding models from the ABI module model registry.
    - Configures `tools` as an empty list.
    - Registers two RAW `Intent` entries with canned guidance responses.
    - Creates defaults when not provided:
      - `AgentConfiguration(system_prompt=GoogleDriveAgent.system_prompt)`
      - `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires `naas_abi_marketplace.applications.google_drive.ABIModule`:
  - Uses `ABIModule.get_instance().engine.services.model_registry`
  - Must have a non-`None` model registry (`assert registry is not None`)
- Model selection:
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.google_drive.agents.GoogleDriveAgent import GoogleDriveAgent

agent = GoogleDriveAgent.New()

print(agent.name)         # Google_Drive
print(agent.description)  # Helps you interact with Google Drive for file storage and management.
```

## Caveats
- `tools` is always configured as `[]`; the agent **cannot** perform Drive operations (list/upload/download/share). It can only provide informational guidance.
- Requires the ABI module engine/model registry to be initialized; otherwise it raises an assertion error (`ModelRegistryService not initialized`).
