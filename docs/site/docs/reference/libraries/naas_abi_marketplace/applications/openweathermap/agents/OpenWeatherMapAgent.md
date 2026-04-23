# OpenWeatherMapAgent

## What it is
- An `IntentAgent` factory and stub agent class configured to provide **general guidance** about OpenWeatherMap (features, weather data, forecasts).
- No OpenWeatherMap tools are configured in this module; it does **not** fetch real weather data.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns an `OpenWeatherMapAgent` with:
    - `NAME`, `DESCRIPTION`
    - `SYSTEM_PROMPT` (explicitly states tools are unavailable)
    - Empty `tools` list
    - Two `IntentType.RAW` intents for informational responses
    - Optional injected `AgentSharedState` and `AgentConfiguration`
- `class OpenWeatherMapAgent(IntentAgent)`
  - No additional methods/overrides; inherits all behavior from `IntentAgent`.

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Chat model dependency (imported inside `create_agent`):
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` (uses `model.model`)
- Module constants:
  - `SYSTEM_PROMPT`: instructs the agent to provide guidance only and acknowledge missing tools.
  - `SUGGESTIONS`: empty list (unused in this file).

## Usage
```python
from naas_abi_marketplace.applications.openweathermap.agents.OpenWeatherMapAgent import create_agent

agent = create_agent()

# Agent can be used via the IntentAgent interface provided by naas_abi_core.
# (Exact invocation depends on the IntentAgent implementation in your environment.)
print(agent.name)         # "OpenWeatherMap"
print(agent.description)  # "Helps you interact with OpenWeatherMap for weather data and forecasts."
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot retrieve live or historical weather data.
- The system prompt explicitly constrains the agent to general information and guidance only.
