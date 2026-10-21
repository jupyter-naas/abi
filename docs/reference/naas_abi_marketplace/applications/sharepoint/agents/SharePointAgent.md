# SharePointAgent

## What it is
A SharePoint-focused `IntentAgent` that provides general guidance about SharePoint document management and collaboration. It does **not** include any tools to access or operate on SharePoint.

## Public API
- `class SharePointAgent(IntentAgent)`
  - An `IntentAgent` configured for SharePoint guidance.
  - Class attributes:
    - `name = "SharePoint"`
    - `description = "Helps you interact with SharePoint for document management and collaboration."`
    - `system_prompt` (guidance-only; explicitly states no tool access)
    - `suggestions = []`

- `SharePointAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> SharePointAgent`
  - Factory constructor that:
    - Fetches default chat and embedding models from the ABIModule model registry.
    - Configures:
      - `tools = []`
      - `intents`: two predefined `IntentType.RAW` intents:
        - “Get information about SharePoint features”
        - “Understand document and site management”
    - Defaults:
      - `AgentConfiguration(system_prompt=SharePointAgent.system_prompt)` if none provided
      - `AgentSharedState(thread_id="0")` if none provided
    - Returns a fully constructed `SharePointAgent` with `memory=None`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on `naas_abi_marketplace.applications.sharepoint.ABIModule`:
  - Uses `ABIModule.get_instance().engine.services.model_registry`
  - Requires the model registry service to be initialized (`assert registry is not None`)
- Model requirements (resolved via registry):
  - `chat_model = registry.get_default_chat_model()`
  - `embedding_model = registry.get_default_embedding_model().model`
- Tools:
  - None (`tools = []`)

## Usage
```python
from naas_abi_marketplace.applications.sharepoint.agents.SharePointAgent import SharePointAgent

agent = SharePointAgent.New()
# Interact with `agent` using the IntentAgent interface from naas_abi_core.
```

## Caveats
- No SharePoint operations can be performed because `tools` is empty and the system prompt explicitly states tool access is unavailable.
- `New()` requires the SharePoint `ABIModule` engine and its `model_registry` to be initialized; otherwise it asserts.
