# XAgent

## What it is
- `XAgent` is an `Agent` specialization for exploring X (Twitter) data.
- It is configured with:
  - A predefined `system_prompt` that routes questions to either X v2 API tools (live data) or SPARQL tools (ingested/knowledge-graph data).
  - A set of SPARQL “competency question” tools loaded from the `templatablesparqlquery` module.

## Public API
### Class: `XAgent(Agent)`
Public class attributes:
- `name: str = "X"` — agent display name.
- `description: str` — agent description.
- `logo_url: str` — logo image URL.
- `suggestions: list[dict]` — UI prompt suggestions (label/value/description).
- `system_prompt: str` — routing and operating guidelines for tool usage.

Public class methods:
- `get_tools() -> list`
  - Loads SPARQL tools by name from `naas_abi_core.modules.templatablesparqlquery`.
  - Returns the resolved tool list (via `templatable_sparql_query_module.get_tools([...])`).

- `New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> XAgent`
  - Factory that:
    - Retrieves the default chat model from the application module’s `engine.services.model_registry`.
    - Loads tools via `XAgent.get_tools()`.
    - Applies defaults:
      - `AgentConfiguration(system_prompt=XAgent.system_prompt)` if not provided.
      - `AgentSharedState(thread_id="0")` if not provided.
    - Returns a fully constructed `XAgent`.

## Configuration/Dependencies
- Depends on `naas_abi_core.services.agent.Agent` for:
  - `Agent`, `AgentConfiguration`, `AgentSharedState`.
- Requires the application module singleton:
  - `naas_abi_marketplace.applications.x.ABIModule.get_instance()`
  - Used to access `engine.modules[...]` and `engine.services.model_registry`.
- SPARQL tools are loaded from:
  - `naas_abi_core.modules.templatablesparqlquery` (expected type: `ABIModule` subclass)
- Tool names expected to exist in the templatable SPARQL query module:
  - `find_top_liked_tweets`, `find_top_retweeted_tweets`, `find_top_impression_tweets`,
    `find_top_engaging_tweets`, `find_tweets_by_author`, `find_tweets_containing_keyword`,
    `find_tweets_in_language`, `find_tweets_since`, `find_tweet_by_id`,
    `find_top_authors_by_tweet_count`, `find_language_distribution`,
    `find_tweets_by_search_query`, `list_ingested_search_queries`.

## Usage
```python
from naas_abi_marketplace.applications.x.agents.XAgent import XAgent

agent = XAgent.New()

# Agent can now be used through the base Agent interface provided by naas_abi_core.
# (Exact invocation methods depend on the Agent implementation.)
```

## Caveats
- `get_tools()` asserts the loaded module instance is a `TemplatableSparqlQueryABIModule`; misconfiguration will raise an `AssertionError`.
- `New()` requires a correctly initialized `ABIModule` engine environment (module singleton, model registry, and templatable SPARQL query module present).
- Although the `system_prompt` mentions X v2 API tools, this file currently wires only SPARQL tools via `get_tools()` (the X API integration wiring is commented out).
