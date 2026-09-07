# GoogleSheetsAgent

## What it is
- An `IntentAgent` specialized in **general guidance** for Google Sheets (features, spreadsheet management, formulas, data analysis best practices).
- **Non-operational** for real Google Sheets access: it registers **no tools** and its system prompt explicitly states it cannot access spreadsheet data.

## Public API
- `class GoogleSheetsAgent(IntentAgent)`
  - Agent metadata (class attributes):
    - `name = "Google_Sheets"`
    - `description = "Helps you interact with Google Sheets for spreadsheet management and data analysis."`
    - `system_prompt`: guidance-only prompt with explicit constraints (no tools / no data access)
    - `suggestions = []`
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GoogleSheetsAgent`
    - Factory to construct a configured `GoogleSheetsAgent`.
    - Resolves models via the application module’s model registry:
      - `chat_model = registry.get_default_chat_model()`
      - `embedding_model = registry.get_default_embedding_model().model`
    - Sets:
      - `tools = []`
      - `intents`: two `IntentType.RAW` intents returning fixed guidance strings
      - Default `AgentConfiguration(system_prompt=cls.system_prompt)` if none provided
      - Default `AgentSharedState(thread_id="0")` if none provided
      - `memory = None`

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires application module initialization to provide a model registry:
  - `from naas_abi_marketplace.applications.google_sheets import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry` (asserts it is initialized)

## Usage
```python
from naas_abi_marketplace.applications.google_sheets.agents.GoogleSheetsAgent import GoogleSheetsAgent

agent = GoogleSheetsAgent.New()

print(agent.name)         # "Google_Sheets"
print(agent.description)  # Helps you interact with Google Sheets for spreadsheet management and data analysis.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot:
  - read/write spreadsheets
  - access Google Sheets APIs
  - operate on real spreadsheet data
- Construction asserts the model registry exists; if not initialized, `New()` will raise an assertion error.
