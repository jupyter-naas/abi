# SalesforceAgent

## What it is
- A minimal `IntentAgent` wrapper configured to provide **general guidance** about Salesforce CRM and sales operations.
- Ships with **no tools**; it cannot access Salesforce data or perform actions.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `SalesforceAgent` instance.
  - Sets:
    - `name`: `"Salesforce"`
    - `description`: `"Helps you interact with Salesforce for CRM and sales operations."`
    - `system_prompt`: `SYSTEM_PROMPT` (if no configuration provided)
    - `tools`: `[]` (no tools)
    - `intents`: two `IntentType.RAW` intents for informational guidance
    - `state`: provided or new `AgentSharedState()`
    - `memory`: `None`
    - `chat_model`: imported from `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`

- `class SalesforceAgent(IntentAgent)`
  - No additional behavior beyond `IntentAgent` (`pass`).

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
  - Chat model import inside `create_agent`:
    - `from naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model`
- Configuration:
  - `SYSTEM_PROMPT` defines role/objective/context and explicitly states **no Salesforce tools are available**.

## Usage
```python
from naas_abi_marketplace.applications.salesforce.agents.SalesforceAgent import create_agent

agent = create_agent()
# Use `agent` according to the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No tools are configured (`tools = []`), so the agent:
  - cannot connect to Salesforce,
  - cannot read/write CRM objects (leads, accounts, opportunities),
  - only provides general information and best-practice guidance.
