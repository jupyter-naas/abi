# GoogleMapsAgent

## What it is
A minimal `IntentAgent` implementation that provides **general guidance** about Google Maps capabilities (features, location services, geocoding). It is configured with **no tools**, so it cannot perform real geocoding, directions, or data retrieval.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `GoogleMapsAgent`.
  - Sets:
    - `name`: `"Google Maps"`
    - `description`: guidance-focused description
    - `system_prompt`: informs users that tools are not available
    - `tools`: empty list (`[]`)
    - `intents`: two raw intents (feature info; location services/geocoding concepts)
    - `state`: provided `AgentSharedState` or a new one
    - `configuration`: provided `AgentConfiguration` or one created with `SYSTEM_PROMPT`
    - `memory`: `None`

- `class GoogleMapsAgent(IntentAgent)`
  - No additional methods or overrides; inherits behavior from `IntentAgent`.

## Configuration/Dependencies
- Depends on core agent framework types:
  - `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentAgent`, `IntentType` from `naas_abi_core.services.agent.IntentAgent`.
- Uses a chat model:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1.model` (passed as `chat_model=model.model`).
- Key constants:
  - `SYSTEM_PROMPT` explicitly states **no access to Google Maps tools**.
  - `SUGGESTIONS` is defined but empty and unused.

## Usage
```python
from naas_abi_marketplace.applications.google_maps.agents.GoogleMapsAgent import create_agent

agent = create_agent()

# Interact with the agent using the IntentAgent interface provided by naas_abi_core.
# (Exact invocation depends on the IntentAgent implementation in your environment.)
print(agent.name)  # "Google Maps"
```

## Caveats
- **No tools are configured** (`tools = []`), so the agent cannot:
  - geocode addresses,
  - fetch maps data,
  - compute directions,
  - retrieve live location information.
- The built-in intents are `IntentType.RAW` with static guidance text (not tool-backed operations).
