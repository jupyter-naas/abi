# AgicapAgent

## What it is
A thin wrapper around `IntentAgent` that creates a pre-configured “Agicap” financial analysis/cash-flow agent wired to Agicap integration tools and a set of tool-routing intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns an `AgicapAgent` configured with:
    - A system prompt embedding available tool names/descriptions
    - A ChatGPT model (`gpt_4_1_mini`)
    - Agicap integration tools (via `as_tools(...)`)
    - A predefined list of `Intent` entries mapping user phrases (FR/EN) to tool targets:
      - `agicap_list_companies`
      - `agicap_get_company_accounts`
      - `agicap_get_balance`
      - `agicap_get_transactions`
      - `agicap_get_debts`
- `class AgicapAgent(IntentAgent)`
  - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- Reads credentials from `naas_abi_marketplace.applications.agicap.ABIModule.get_instance().configuration`:
  - `agicap_username`
  - `agicap_password`
  - `agicap_bearer_token`
  - `agicap_client_id`
  - `agicap_client_secret`
  - `agicap_api_token`
- Tooling:
  - `AgicapIntegrationConfiguration` + `as_tools` from `...integrations.AgicapIntegration`
- Model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
- Core agent framework types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`

## Usage
```python
from naas_abi_marketplace.applications.agicap.agents.AgicapAgent import create_agent

agent = create_agent()
# Use `agent` according to the IntentAgent interface in naas_abi_core.
```

## Caveats
- This module assumes `ABIModule` is properly configured with Agicap credentials; it does not validate or error-handle missing/invalid credentials in this file.
- `AgicapAgent` adds no custom methods; behavior depends entirely on `IntentAgent` and the configured tools/intents.
