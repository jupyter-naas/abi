# ExchangeRatesAPIAgent

## What it is
- An `IntentAgent` implementation for providing guidance about currency exchange rates and the ExchangeRatesAPI service.
- Includes a factory-style constructor (`New`) that:
  - Retrieves default chat/embedding models from the module engine’s model registry.
  - Builds ExchangeRatesAPI tools via the ExchangeRatesAPI integration (using an API key from module configuration).
  - Injects the tool list into the agent system prompt.
  - Registers a small set of predefined “raw” intents.

## Public API
- `class ExchangeRatesAPIAgent(IntentAgent)`
  - Class attributes:
    - `name`: `"ExchangeRatesAPI"`
    - `description`: `"Helps you interact with ExchangeRatesAPI for currency exchange rate information."`
    - `system_prompt`: Instruction prompt with a `[TOOLS]` placeholder that is filled at construction time.
    - `suggestions`: empty list (`[]`)
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> ExchangeRatesAPIAgent`
    - Creates and returns an initialized agent instance.
    - Populates tools via `ExchangeratesapiIntegration.as_tools(...)`.
    - Creates two `IntentType.RAW` intents related to exchange rates and currency conversion.
    - Uses `AgentConfiguration(system_prompt=...)` if none is provided.
    - Uses `AgentSharedState(thread_id="0")` if none is provided.

## Configuration/Dependencies
- Configuration:
  - `ABIModule.get_instance().configuration.exchangeratesapi_api_key` (used to configure integration tools)
- Dependencies (imports/usage):
  - `naas_abi_core.services.agent.IntentAgent`:
    - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
  - `naas_abi_marketplace.applications.exchangeratesapi.ABIModule`:
    - Provides module instance, configuration, and engine services
  - `naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration`:
    - `ExchangeratesapiIntegrationConfiguration`, `as_tools`
- Runtime requirement:
  - `abi_module.engine.services.model_registry` must be initialized (asserted in `New`).

## Usage
```python
from naas_abi_marketplace.applications.exchangeratesapi.agents.ExchangeRatesAPIAgent import (
    ExchangeRatesAPIAgent,
)

agent = ExchangeRatesAPIAgent.New()

# Interact with `agent` through the IntentAgent interface (methods defined in naas_abi_core).
```

## Caveats
- The default `system_prompt` states the agent “currently do not have access to ExchangeRatesAPI tools” and should not retrieve real-time data; however, `New()` still attaches tools produced by `as_tools(...)` and injects them into the prompt.
- If the module engine’s `model_registry` is not initialized, `New()` will raise an assertion error.
