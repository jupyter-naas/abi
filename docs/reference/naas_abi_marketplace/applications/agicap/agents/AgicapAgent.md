# AgicapAgent

## What it is
An `IntentAgent` subclass preconfigured as an “Agicap” cash-flow and financial analysis agent. It wires Agicap integration tools, a tool-aware system prompt, and a set of intent-to-tool routes (FR/EN).

## Public API
- `class AgicapAgent(IntentAgent)`
  - Predefined class attributes:
    - `name = "Agicap"`
    - `description = "Expert cash flow management and financial analysis agent with access to Agicap Integration tools."`
    - `avatar_url = "https://agicap.com/favicon.ico"`
    - `system_prompt`: templated prompt that is populated with available tool names/descriptions
    - `suggestions: list = []`
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> AgicapAgent`
    - Builds and returns an `AgicapAgent` instance configured with:
      - Default chat model from the engine model registry
      - Default embedding model from the engine model registry
      - Agicap integration tools via `as_tools(AgicapIntegrationConfiguration(...))`
      - A system prompt where `[TOOLS]` is replaced by a bullet list of tool names/descriptions
      - A fixed list of `Intent` routes mapping phrases to tool targets:
        - `agicap_list_companies`
        - `agicap_get_company_accounts`
        - `agicap_get_balance`
        - `agicap_get_transactions`
        - `agicap_get_debts`
    - Defaults:
      - If `agent_configuration` is `None`: `AgentConfiguration(system_prompt=...)`
      - If `agent_shared_state` is `None`: `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Requires an initialized `ABIModule` singleton:
  - `from naas_abi_marketplace.applications.agicap import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry` to fetch:
    - `get_default_chat_model()`
    - `get_default_embedding_model().model`
- Reads Agicap credentials from `ABIModule.get_instance().configuration`:
  - `agicap_username`
  - `agicap_password`
  - `agicap_bearer_token`
  - `agicap_client_id`
  - `agicap_client_secret`
  - `agicap_api_token`
- Tooling dependency:
  - `AgicapIntegrationConfiguration`, `as_tools` from `...integrations.AgicapIntegration`
- Core agent framework types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`

## Usage
```python
from naas_abi_marketplace.applications.agicap.agents.AgicapAgent import AgicapAgent

agent = AgicapAgent.New()
# Interact with `agent` using the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- Assumes `ABIModule` is properly configured and the engine model registry is initialized; it asserts `model_registry` is not `None`.
- No validation of missing/invalid Agicap credentials is performed in this module.
- `AgicapAgent` adds no custom runtime logic beyond construction/configuration; behavior depends on `IntentAgent`, selected models, and provided tools.
