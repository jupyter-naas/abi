# GitHubAgent

## What it is
An `IntentAgent` subclass preconfigured to interact with GitHub using REST and GraphQL tool integrations. It builds its system prompt dynamically by injecting the available tool names and descriptions.

## Public API
- `class GitHubAgent(IntentAgent)`
  - Agent metadata:
    - `name = "GitHub"`
    - `description`: GitHub REST/GraphQL assistance
    - `avatar_url`: GitHub mark image URL
    - `system_prompt`: structured prompt template containing a `[TOOLS]` placeholder
    - `suggestions = []`
- `GitHubAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GitHubAgent`
  - Factory constructor that:
    - Loads default chat and embedding models from `ABIModule.get_instance().engine.services.model_registry`
    - Reads `github_access_token` from `ABIModule.get_instance().configuration.github_access_token`
    - Builds tool list from:
      - `naas_abi_marketplace.applications.github.integrations.GitHubIntegration.as_tools`: the read tools (`READ_TOOLS`) and, besides, only the write tools the module configuration names in `agent_write_tools`
      - `naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration.as_tools`
    - Limits every REST call to the module's `repositories` ("owner/repo") when that list is not empty
    - Injects tool descriptions into `system_prompt` (replacing `[TOOLS]`)
    - Defaults:
      - `AgentConfiguration(system_prompt=...)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided
    - Instantiates and returns `GitHubAgent(..., intents=..., memory=None)`, keeping the tool intents of `INTENTS` whose tool it carries

## Configuration/Dependencies
- Requires the GitHub application module:
  - `from naas_abi_marketplace.applications.github import ABIModule`
  - Must provide `ABIModule.get_instance().configuration.github_access_token`
  - Optional `agent_write_tools: list[str]` (default empty) and `repositories: list[str]` (default empty: any repository the token reaches)
- Requires model registry service to be initialized:
  - `abi_module.engine.services.model_registry` must not be `None` (asserted)
  - Uses:
    - `registry.get_default_chat_model()`
    - `registry.get_default_embedding_model().model`
- Intents are imported from:
  - `naas_abi_marketplace.applications.github.agents.intents.GitHubAgentIntents.INTENTS`
- Tools come from REST/GraphQL integration `as_tools(...)` functions with configurations initialized using the access token.

## Usage
```python
from naas_abi_marketplace.applications.github.agents.GitHubAgent import GitHubAgent

agent = GitHubAgent.New()
# Use the returned IntentAgent according to your naas_abi_core runtime/orchestration.
```

## Caveats
- Everyone who may use the agent acts with the module's one token: keep `agent_write_tools` to what every such user may do, and `repositories` to what they may see.
- `GitHubAgent.New()` asserts that the model registry service is initialized; it will raise an `AssertionError` otherwise.
- A GitHub access token is required via `ABIModule` configuration; tool creation depends on it.
- The prompt tool list is generated from whatever the integrations return via `as_tools(...)`.
