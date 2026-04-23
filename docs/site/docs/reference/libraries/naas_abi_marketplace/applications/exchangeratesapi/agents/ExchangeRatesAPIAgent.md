# ExchangeRatesAPIAgent

## What it is
- An `IntentAgent` factory and thin agent class for interacting with (or guiding use of) the ExchangeRatesAPI service.
- Builds an agent configured with:
  - A system prompt describing constraints and capabilities.
  - Tool definitions derived from an ExchangeRatesAPI integration (configured via API key).
  - A small set of predefined “raw” intents for exchange-rate guidance.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Creates and returns an `ExchangeRatesAPIAgent` instance.
  - Loads API key from the application module configuration.
  - Registers tools from `ExchangeratesapiIntegration.as_tools(...)`.
  - Injects tool names/descriptions into the system prompt.
  - Uses the `gpt_4_1` chat model.

- `class ExchangeRatesAPIAgent(IntentAgent)`
  - No additional methods or overrides (inherits behavior from `IntentAgent`).

## Configuration/Dependencies
- Configuration source:
  - `ABIModule.get_instance().configuration.exchangeratesapi_api_key` (API key used to configure the integration tools).
- External dependencies (imported/used):
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
  - Chat model:
    - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model`
  - Integration tooling:
    - `naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration`:
      - `as_tools`, `ExchangeratesapiIntegrationConfiguration`

## Usage
```python
from naas_abi_marketplace.applications.exchangeratesapi.agents.ExchangeRatesAPIAgent import create_agent

agent = create_agent()
# Use `agent` via the IntentAgent interface provided by naas_abi_core.
```

## Caveats
- The system prompt explicitly states the agent “currently do not have access to ExchangeRatesAPI tools” and should only provide general guidance; however, the factory **does** attach tools via `as_tools(...)` if available and configured.
- Real-time rates and conversions depend on correct API key configuration and the behavior of the integration tools (not defined in this file).
