# SpotifyAgent

## What it is
A minimal `IntentAgent` implementation for Spotify-related guidance (features, playlists, discovery). It is explicitly **tool-less**, so it cannot access Spotify data or perform real operations.

## Public API
- `class SpotifyAgent(IntentAgent)`
  - Agent definition with preset metadata:
    - `name = "Spotify"`
    - `description = "Helps you interact with Spotify for music streaming and playlist management."`
    - `system_prompt` describing scope/constraints
    - `suggestions = []`
- `SpotifyAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> SpotifyAgent`
  - Factory constructor that:
    - retrieves default chat and embedding models via the application `ABIModule` model registry
    - configures **no tools** (`tools = []`)
    - registers a small set of raw `Intent`s
    - initializes default state/config when not provided

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Depends on marketplace Spotify module:
  - `from naas_abi_marketplace.applications.spotify import ABIModule`
  - Uses `ABIModule.get_instance().engine.services.model_registry`
    - Requires model registry to be initialized (`assert registry is not None`)
  - Models used:
    - `chat_model = registry.get_default_chat_model()`
    - `embedding_model = registry.get_default_embedding_model().model`
- Defaults:
  - `agent_configuration`: `AgentConfiguration(system_prompt=SpotifyAgent.system_prompt)`
  - `agent_shared_state`: `AgentSharedState(thread_id="0")`
- Tools/Memory:
  - `tools = []`
  - `memory = None`

## Usage
```python
from naas_abi_marketplace.applications.spotify.agents.SpotifyAgent import SpotifyAgent

agent = SpotifyAgent.New()

# Interaction methods are provided by IntentAgent (naas_abi_core), not by this file.
# The agent is configured for general Spotify guidance without tool access.
```

## Caveats
- No Spotify tools are configured; the agent cannot:
  - access accounts, playlists, tracks, or playback data
  - perform playlist/track mutations
- Requires a properly initialized `ABIModule` engine and `model_registry`; otherwise `SpotifyAgent.New()` will assert.
