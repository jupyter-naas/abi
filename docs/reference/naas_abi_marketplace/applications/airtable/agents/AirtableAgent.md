# AirtableAgent

## What it is
An `IntentAgent` specialized for providing general guidance about Airtable (databases, records, collaboration). It does **not** wire any Airtable tools, so it cannot access or modify Airtable data.

## Public API
- `class AirtableAgent(IntentAgent)`
  - Agent definition with preset:
    - `name = "Airtable"`
    - `description = "Helps you interact with Airtable for database and spreadsheet management."`
    - `system_prompt` describing scope and constraints (no tool access)
    - `suggestions = []`

- `AirtableAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> AirtableAgent`
  - Factory that:
    - Fetches the default chat and embedding models from the application `ModelRegistryService`.
    - Configures `tools=[]`.
    - Adds two predefined `IntentType.RAW` intents with informational responses.
    - Creates default `AgentConfiguration(system_prompt=...)` if not provided.
    - Creates default `AgentSharedState(thread_id="0")` if not provided.

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Runtime dependency inside `New`:
  - `naas_abi_marketplace.applications.airtable.ABIModule.get_instance()`
  - Uses `abi_module.engine.services.model_registry`:
    - `get_default_chat_model()`
    - `get_default_embedding_model().model`
- Requires the model registry to be initialized (asserts non-`None`).

## Usage
```python
from naas_abi_marketplace.applications.airtable.agents.AirtableAgent import AirtableAgent

agent = AirtableAgent.New()
# Interact with `agent` using the IntentAgent interface from naas_abi_core.
```

## Caveats
- No tools are configured (`tools=[]`), so the agent cannot perform Airtable operations or access Airtable data.
- `New()` asserts that `ModelRegistryService` is initialized; otherwise it raises an `AssertionError`.
- `suggestions` is defined but unused in this file.
