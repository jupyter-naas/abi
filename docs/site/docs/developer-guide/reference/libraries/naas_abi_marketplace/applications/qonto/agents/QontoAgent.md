# QontoAgent

## What it is
A minimal `IntentAgent` configuration for a Qonto-focused assistant that **only provides general guidance** about Qonto, business banking, and account management (no tools are configured).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a `QontoAgent` with:
    - Name/description constants
    - A GPT-4.1 chat model
    - No tools (`tools = []`)
    - Two predefined RAW intents (informational responses)
    - Optional shared state and configuration (defaults created if not provided)
- `class QontoAgent(IntentAgent)`
  - Concrete agent type (no additional behavior beyond `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Loads the chat model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1`
- Key constants:
  - `SYSTEM_PROMPT`: explicitly states no access to Qonto tools/data; guidance-only behavior.
  - `SUGGESTIONS`: empty list.

## Usage
```python
from naas_abi_marketplace.applications.qonto.agents.QontoAgent import create_agent

agent = create_agent()
# Use `agent` according to the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- No Qonto tools are configured (`tools = []`), so the agent cannot:
  - Access accounts, balances, transactions, or perform any banking actions.
- Intended output is informational guidance based on the system prompt and RAW intents.
