# GitHubAgent

## What it is
A factory and thin agent wrapper that builds an `IntentAgent` configured to interact with GitHub via provided REST and GraphQL tool integrations, using a predefined system prompt and a set of tool-backed intents.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Creates and returns a configured `GitHubAgent` instance.
  - Wires:
    - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
    - Tools: REST + GraphQL GitHub integrations (converted to tool objects)
    - Intents: a fixed list of tool intents (e.g., repo, issues, PRs, secrets)
    - System prompt: `SYSTEM_PROMPT` with an injected `[TOOLS]` section listing tool names/descriptions.
  - Uses provided `AgentSharedState` / `AgentConfiguration` if supplied, otherwise creates defaults.

- `class GitHubAgent(IntentAgent)`
  - Subclass of `IntentAgent` with no additional behavior (placeholder).

## Configuration/Dependencies
- Requires `ABIModule.get_instance().configuration.github_access_token` to exist; it is passed to:
  - `GitHubIntegrationConfiguration(access_token=...)` (REST tools)
  - `GitHubGraphqlIntegrationConfiguration(access_token=...)` (GraphQL tools)
- Depends on `naas_abi_core.services.agent.IntentAgent` types:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Tools are sourced from:
  - `naas_abi_marketplace.applications.github.integrations.GitHubIntegration.as_tools`
  - `naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration.as_tools`

## Usage
```python
from naas_abi_marketplace.applications.github.agents.GitHubAgent import create_agent

agent = create_agent()
# Agent is now configured with GitHub tools and intents.
# How you run/send messages depends on the IntentAgent runtime in naas_abi_core.
```

## Caveats
- The returned `GitHubAgent` behavior is entirely defined by `IntentAgent` plus configured tools/intents; `GitHubAgent` itself adds no methods.
- The system prompt dynamically lists available tools; tool availability depends on integration `as_tools(...)` output and a valid GitHub access token.
