# YfinanceAgent

## What it is
A thin `IntentAgent` wrapper configured for Yahoo Finance research workflows. It wires a chat model, yfinance-backed tools, and a set of tool intents into an `IntentAgent` instance via `create_agent()`.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `YfinanceAgent`:
    - Loads the chat model (`gpt_4_1_mini`).
    - Instantiates Yahoo Finance integration tools via `as_tools(...)`.
    - Defines tool-based intents (ticker search, info, history, financials, sector, industry).
    - Assembles a system prompt that includes the available tool names/descriptions.
    - Applies default `AgentConfiguration` and `AgentSharedState` when not provided.

- `class YfinanceAgent(IntentAgent)`
  - No additional behavior; inherits all functionality from `IntentAgent`.

## Configuration/Dependencies
- Core agent framework:
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Model dependency:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
- Yahoo Finance integration:
  - `naas_abi_marketplace.applications.yahoofinance.integrations.YfinanceIntegration`:
    - `YfinanceIntegrationConfiguration`, `as_tools`

Constants used to configure the agent:
- `NAME = "YahooFinance"`
- `DESCRIPTION = "..."`
- `AVATAR_URL = "..."` (declared but not used in `create_agent`)
- `SYSTEM_PROMPT` (templated; `[TOOLS]` replaced with tool list)

## Usage
```python
from naas_abi_marketplace.applications.yahoofinance.agents.YfinanceAgent import create_agent

agent = create_agent()
# Use `agent` through the IntentAgent interface provided by naas_abi_core
```

## Caveats
- `YfinanceAgent` itself adds no custom methods; all runtime behavior comes from `IntentAgent`, the loaded model, and the yfinance integration tools.
- The configured system prompt constrains the agent to use provided yfinance tools for data retrieval and to avoid investment advice.
