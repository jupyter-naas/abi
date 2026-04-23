# YouTubeAgent

## What it is
A minimal `IntentAgent` implementation for YouTube-related guidance. It provides predefined informational intents and explicitly has **no YouTube tools configured**, so it can only offer general guidance (not perform actions).

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Factory that builds and returns a configured `YouTubeAgent`.
  - Sets:
    - `name`: `"YouTube"`
    - `description`: `"Helps you interact with YouTube for video management and channel operations."`
    - `system_prompt`: `SYSTEM_PROMPT` (unless a configuration is provided)
    - `tools`: empty list (`[]`)
    - `intents`: two raw informational intents
    - `state`: provided `AgentSharedState` or a new one
    - `memory`: `None`

- `class YouTubeAgent(IntentAgent)`
  - Concrete agent class (no additional behavior beyond `IntentAgent`).

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Uses ChatGPT model from:
  - `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1 import model`
- Constants:
  - `NAME`, `DESCRIPTION`, `SYSTEM_PROMPT`, `SUGGESTIONS` (empty)

## Usage
```python
from naas_abi_marketplace.applications.youtube.agents.YouTubeAgent import create_agent

agent = create_agent()
# agent is an IntentAgent (YouTubeAgent) configured with a system prompt and two intents.
```

## Caveats
- No tools are configured (`tools = []`), so the agent **cannot** access YouTube, manage videos, playlists, or channel data.
- The provided intents are informational only (`IntentType.RAW`) and return static guidance strings.
