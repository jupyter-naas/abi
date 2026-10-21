# GoogleMapsAgent

## What it is
A minimal `IntentAgent` for providing **general guidance** about Google Maps concepts (features, location services, geocoding). It configures **no tools**, so it cannot perform real geocoding, directions, or data retrieval.

## Public API
- `class GoogleMapsAgent(IntentAgent)`
  - Inherits all behavior from `IntentAgent`.
  - Class attributes:
    - `name = "Google Maps"`
    - `description = "Helps you interact with Google Maps for location services and geocoding."`
    - `system_prompt`: guidance-focused prompt explicitly stating tools are unavailable
    - `suggestions = []` (defined but empty)

- `GoogleMapsAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GoogleMapsAgent`
  - Factory constructor that:
    - Gets the application `ABIModule` singleton and uses its `engine.services.model_registry` to load:
      - default chat model
      - default embedding model (`.model`)
    - Creates:
      - `tools = []`
      - Two `IntentType.RAW` intents with static explanatory targets
    - Defaults:
      - `AgentConfiguration(system_prompt=GoogleMapsAgent.system_prompt)` when not provided
      - `AgentSharedState(thread_id="0")` when not provided
    - Returns a configured `GoogleMapsAgent` with `memory=None`.

## Configuration/Dependencies
- Imports from `naas_abi_core.services.agent.IntentAgent`:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType`
- Requires `naas_abi_marketplace.applications.google_maps.ABIModule`:
  - Must provide `engine.services.model_registry`
  - `model_registry` must be initialized (`assert registry is not None`)

## Usage
```python
from naas_abi_marketplace.applications.google_maps.agents.GoogleMapsAgent import GoogleMapsAgent

agent = GoogleMapsAgent.New()

print(agent.name)         # "Google Maps"
print(agent.description)  # Helps you interact with Google Maps for location services and geocoding.
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot:
  - geocode addresses,
  - fetch maps/location data,
  - compute directions.
- `New()` depends on a properly initialized `ABIModule` and `model_registry`; otherwise it will assert.
