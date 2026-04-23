# GoogleSheetsAgent

## What it is
- An `IntentAgent` specialized for providing **general guidance** about Google Sheets: spreadsheet management, formulas, and data analysis.
- This agent is **non-operational for real Sheet access**: it defines **no tools** and explicitly states it cannot access spreadsheets.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that constructs and returns a configured `GoogleSheetsAgent`.
  - Sets:
    - `name`: `"Google_Sheets"`
    - `description`: guidance-focused description
    - `system_prompt`: `SYSTEM_PROMPT`
    - `tools`: empty list (`[]`)
    - `intents`: two `IntentType.RAW` intents for feature info and spreadsheet/formula guidance
    - `chat_model`: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model.model`
    - `state`: provided `AgentSharedState` or a new instance
    - `memory`: `None`

- `class GoogleSheetsAgent(IntentAgent)`
  - No additional methods/overrides; inherits behavior from `IntentAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses a ChatGPT model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
- Key constants:
  - `SYSTEM_PROMPT`: instructs the agent to provide guidance only and acknowledge lack of tools.
  - `SUGGESTIONS`: empty list (unused in this file).

## Usage
```python
from naas_abi_marketplace.applications.google_sheets.agents.GoogleSheetsAgent import create_agent

agent = create_agent()

# The agent is configured with no tools; it can provide general guidance only.
print(agent.name)         # "Google_Sheets"
print(agent.description)  # Helps you interact with Google Sheets...
```

## Caveats
- No Google Sheets tools are configured (`tools = []`), so the agent **cannot**:
  - access spreadsheets
  - read/write data
  - perform actions against Google Sheets APIs
- The intents are `RAW` and return predefined guidance-style responses rather than executing operations.
