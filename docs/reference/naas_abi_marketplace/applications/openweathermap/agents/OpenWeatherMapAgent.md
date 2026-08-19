# OpenWeatherMapAgent

## What it is
- An `IntentAgent` implementation for providing **general guidance** about OpenWeatherMap (features, weather data concepts, forecasts).
- This agent is **not connected to OpenWeatherMap tools/APIs** in this module and therefore **cannot retrieve live weather data**.

## Public API
- `class OpenWeatherMapAgent(IntentAgent)`
  - Class attributes:
    - `name`: `"OpenWeatherMap"`
    - `description`: `"Helps you interact with OpenWeatherMap for weather data and forecasts."`
    - `system_prompt`: System instructions emphasizing guidance-only behavior and no tool access.
    - `suggestions`: empty list
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> OpenWeatherMapAgent`
    - Factory that constructs and returns a configured `OpenWeatherMapAgent`.
    - Initializes:
      - `chat_model` and `embedding_model` from the application `ModelRegistryService` (via `ABIModule`).
      - `tools` as an empty list.
      - Two `IntentType.RAW` intents with pre-defined informational targets.
      - Defaults:
        - `agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)` if not provided
        - `agent_shared_state = AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent` for:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Runtime dependency on the OpenWeatherMap application module:
  - `from naas_abi_marketplace.applications.openweathermap import ABIModule`
  - Requires `ABIModule.get_instance().engine.services.model_registry` to be initialized.
  - Uses:
    - `registry.get_default_chat_model()`
    - `registry.get_default_embedding_model().model`

## Usage
```python
from naas_abi_marketplace.applications.openweathermap.agents.OpenWeatherMapAgent import OpenWeatherMapAgent

agent = OpenWeatherMapAgent.New()

print(agent.name)
print(agent.description)
```

## Caveats
- `tools` is always `[]` in `New()`, so the agent cannot fetch or act on real OpenWeatherMap data.
- `New()` asserts that the model registry is initialized:
  - `assert registry is not None, "ModelRegistryService not initialized"`
