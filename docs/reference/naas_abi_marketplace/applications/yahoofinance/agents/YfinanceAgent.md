# YfinanceAgent

## What it is
An `IntentAgent` subclass preconfigured for Yahoo Finance–based market research. It boots with the default chat/embedding models from the application engine, wires in `yfinance` integration tools, and registers tool-driven intents for common finance queries.

## Public API
- `class YfinanceAgent(IntentAgent)`
  - Predefined class attributes:
    - `name = "YahooFinance"`
    - `description = "Expert financial analyst agent ... using Yahoo Finance."`
    - `avatar_url = "https://.../yahoo_finance_logo.png"`
    - `system_prompt` (template containing `[TOOLS]` placeholder)
    - `suggestions: list = []`
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> YfinanceAgent`
    - Creates and returns a configured agent instance:
      - Fetches the default chat model and embedding model via the app module engine registry.
      - Builds Yahoo Finance tools via `YfinanceIntegrationConfiguration()` and `as_tools(...)`.
      - Registers tool intents targeting:
        - `yfinance_search_ticker`
        - `yfinance_get_ticker_info`
        - `yfinance_get_ticker_history`
        - `yfinance_get_ticker_financials`
        - `yfinance_get_sector_info`
        - `yfinance_get_industry_info`
      - Renders `system_prompt` by replacing `[TOOLS]` with a list of tool names/descriptions.
      - Defaults:
        - `AgentConfiguration(system_prompt=rendered_prompt)` if not provided
        - `AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
- Agent framework:
  - `naas_abi_core.services.agent.IntentAgent`: `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Application module / engine:
  - `naas_abi_marketplace.applications.yahoofinance.ABIModule` (used to access `engine.services.model_registry`)
- Yahoo Finance integration:
  - `naas_abi_marketplace.applications.yahoofinance.integrations.YfinanceIntegration`:
    - `YfinanceIntegrationConfiguration`
    - `as_tools`

## Usage
```python
from naas_abi_marketplace.applications.yahoofinance.agents.YfinanceAgent import YfinanceAgent

agent = YfinanceAgent.New()
# Interact with `agent` through the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- Requires the Yahoo Finance `ABIModule` engine and its `model_registry` to be initialized; otherwise `New()` asserts with `"ModelRegistryService not initialized"`.
- If you pass a custom `AgentConfiguration`, its `system_prompt` is not automatically overwritten with the rendered `[TOOLS]` prompt.
