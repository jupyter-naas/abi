# YouTubeAgent

## What it is
A minimal `IntentAgent` implementation for YouTube-related guidance. It defines a YouTube-focused system prompt and two static informational intents, but configures **no tools**, so it cannot perform YouTube actions.

## Public API
- `class YouTubeAgent(IntentAgent)`
  - Agent class with predefined:
    - `name = "YouTube"`
    - `description = "Helps you interact with YouTube for video management and channel operations."`
    - `system_prompt` describing guidance-only behavior (no tool access)
    - `suggestions = []`

- `YouTubeAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> YouTubeAgent`
  - Factory constructor that:
    - Retrieves default chat and embedding models from the marketplace engine model registry.
    - Sets `tools = []`.
    - Sets `intents` to two `IntentType.RAW` intents with static guidance strings.
    - Defaults:
      - `agent_configuration = AgentConfiguration(system_prompt=YouTubeAgent.system_prompt)`
      - `agent_shared_state = AgentSharedState(thread_id="0")`
    - Returns a configured `YouTubeAgent` with `memory=None`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires marketplace module initialization:
  - `from naas_abi_marketplace.applications.youtube import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
  - Assumes registry is initialized (`assert registry is not None`)

## Usage
```python
from naas_abi_marketplace.applications.youtube.agents.YouTubeAgent import YouTubeAgent

agent = YouTubeAgent.New()
print(agent.name)  # "YouTube"
```

## Caveats
- No tools are configured (`tools = []`), so the agent cannot upload/manage videos, playlists, or channels.
- Requires a configured/initialized engine `model_registry`; otherwise `assert registry is not None` will fail.
- Intents are `IntentType.RAW` and provide static text responses only.
