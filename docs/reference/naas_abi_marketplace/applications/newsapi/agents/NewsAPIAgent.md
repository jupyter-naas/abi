# NewsAPIAgent

## What it is
- An `IntentAgent` implementation for the NewsAPI application.
- Provides **guidance-only** information about NewsAPI (features, search concepts, media monitoring).
- **No NewsAPI tools are configured**, so it cannot retrieve live articles/headlines.

## Public API
- `class NewsAPIAgent(IntentAgent)`
  - Agent definition with:
    - `name = "NewsAPI"`
    - `description = "Helps you interact with NewsAPI for news articles and headlines."`
    - `system_prompt` describing guidance-only behavior and constraints
    - `suggestions = []`

- `NewsAPIAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> NewsAPIAgent` (classmethod)
  - Factory that:
    - Loads the application `ABIModule` singleton.
    - Pulls the default chat model and default embedding model from the engine’s model registry.
    - Configures:
      - `tools = []`
      - Two informational `IntentType.RAW` intents:
        - “Get information about NewsAPI features”
        - “Understand news search and article retrieval”
    - Creates defaults when not provided:
      - `AgentConfiguration(system_prompt=cls.system_prompt)`
      - `AgentSharedState(thread_id="0")`

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.IntentAgent`:
  - `IntentAgent`, `AgentConfiguration`, `AgentSharedState`, `Intent`, `IntentType`
- Requires the NewsAPI application module:
  - `naas_abi_marketplace.applications.newsapi.ABIModule.get_instance()`
- Requires an initialized model registry service:
  - Uses `abi_module.engine.services.model_registry`
  - Asserts registry is initialized (`assert registry is not None`)

## Usage
```python
from naas_abi_marketplace.applications.newsapi.agents.NewsAPIAgent import NewsAPIAgent

agent = NewsAPIAgent.New()
print(agent.name)
print(agent.description)
```

## Caveats
- `tools` is an empty list, so the agent **cannot** call NewsAPI or fetch real articles/headlines.
- Requires a functioning `ABIModule` and initialized model registry; otherwise `New()` will assert/fail.
