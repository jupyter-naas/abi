# GoogleSearchAgent

## What it is
An `IntentAgent` specialized for web search using **Google Programmable Search Engine**, with additional tools for finding **LinkedIn profile** and **LinkedIn organization** pages. It builds a tool list and intent routing, and injects available tools into its system prompt.

## Public API
- `class GoogleSearchAgent(IntentAgent)`
  - Agent metadata:
    - `name = "Google_Search"`
    - `description = "Search the web using Google Programmable Search Engine."`
    - `avatar_url = "..."`
    - `system_prompt`: instructions including tool usage rules and result formatting expectations
    - `suggestions`: UI prompt suggestions for common searches
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GoogleSearchAgent`
    - Creates and returns a configured `GoogleSearchAgent`.
    - Resolves default chat and embedding models from the module engine’s model registry.
    - Builds tools:
      - Google Programmable Search Engine integration tools
      - LinkedIn profile search workflow tools
      - LinkedIn organization search workflow tools
    - Configures `Intent` routes to specific tool targets:
      - Web search → `googlesearch_query`
      - LinkedIn profile search → `googlesearch_search_linkedin_profile_page`
      - LinkedIn organization search → `googlesearch_search_linkedin_organization_page`
    - Replaces `[TOOLS]` in `system_prompt` with a bullet list of `tool.name: tool.description`.
    - Defaults:
      - `AgentConfiguration(system_prompt=...)` if not provided
      - `AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
- **Module singleton**
  - `naas_abi_marketplace.applications.google_search.ABIModule.get_instance()`
- **Required configuration values** (read from `ABIModule.get_instance().configuration`)
  - `google_custom_search_api_key`
  - `google_custom_search_engine_id`
- **Model registry dependency**
  - `abi_module.engine.services.model_registry` must be initialized (asserted)
  - Uses:
    - `registry.get_default_chat_model()`
    - `registry.get_default_embedding_model().model`
- **Tools and workflows**
  - `GoogleProgrammableSearchEngineIntegrationConfiguration(api_key, search_engine_id)`
  - `as_tools(google_programmable_search_engine_integration_config)`
  - `SearchLinkedInProfilePageWorkflow(...).as_tools()`
  - `SearchLinkedInOrganizationPageWorkflow(...).as_tools()`

## Usage
```python
from naas_abi_marketplace.applications.google_search.agents.GoogleSearchAgent import (
    GoogleSearchAgent,
)

agent = GoogleSearchAgent.New()

# Interact with the agent via the IntentAgent interface (methods depend on naas_abi_core).
# For example, pass a user message into whatever runner/chat loop your platform provides.
```

## Caveats
- `ABIModule.engine.services.model_registry` must be available; otherwise `New()` raises an assertion error.
- Missing/invalid `google_custom_search_api_key` or `google_custom_search_engine_id` will lead to improperly configured search tools (no validation is performed here).
- This module defines `New()` (factory) but does not define a `create_agent()` function.
