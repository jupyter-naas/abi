# SpotifyAgent

## What it is
A minimal `IntentAgent` implementation configured to provide **general guidance** about Spotify features, playlist management concepts, and music discovery. It does **not** include Spotify API/tools access.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `SpotifyAgent` with:
    - system prompt (`SYSTEM_PROMPT`)
    - zero tools (`tools = []`)
    - a small set of predefined raw intents
    - optional shared state and configuration
- `class SpotifyAgent(IntentAgent)`
  - Concrete agent class (no additional behavior; inherits everything from `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses a chat model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1` (imported inside `create_agent`)
- Configuration defaults:
  - If `agent_configuration` is not provided, it uses `AgentConfiguration(system_prompt=SYSTEM_PROMPT)`.
  - If `agent_shared_state` is not provided, it creates a new `AgentSharedState()`.
- Tools:
  - None configured (`tools = []`), so the agent must not perform real Spotify operations.

## Usage
```python
from naas_abi_marketplace.applications.spotify.agents.SpotifyAgent import create_agent

agent = create_agent()

# How you invoke the agent depends on IntentAgent's interface in naas_abi_core.
# The agent is configured to answer with general Spotify guidance (no tool access).
```

## Caveats
- No Spotify tools are configured; the agent cannot:
  - access Spotify accounts/data
  - manage real playlists/tracks
  - perform playback or API operations
- Responses are limited to general information and conceptual guidance per `SYSTEM_PROMPT`.
