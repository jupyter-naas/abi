# AirtableAgent

## What it is
A minimal `IntentAgent` implementation configured to provide general guidance about Airtable (no Airtable tools are wired in).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns an `AirtableAgent` with:
    - A predefined system prompt describing constraints (no tool access).
    - No tools (`tools=[]`).
    - Two predefined RAW intents providing informational responses.
    - A ChatGPT model imported from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`.

- `class AirtableAgent(IntentAgent)`
  - Concrete agent type (no additional behavior beyond `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Depends on model module:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (uses `model.model`)
- Key constants:
  - `NAME = "Airtable"`
  - `DESCRIPTION = "Helps you interact with Airtable for database and spreadsheet management."`
  - `SYSTEM_PROMPT` (states the agent has no Airtable tool access)
  - `SUGGESTIONS: list = []` (defined but unused in this file)

## Usage
```python
from naas_abi_marketplace.applications.airtable.agents.AirtableAgent import create_agent

agent = create_agent()
# Use `agent` via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No Airtable tools are configured (`tools=[]`), so the agent cannot access or modify Airtable data; it only provides general information and guidance.
- `AirtableAgent` adds no methods of its own; all behavior is inherited from `IntentAgent`.
