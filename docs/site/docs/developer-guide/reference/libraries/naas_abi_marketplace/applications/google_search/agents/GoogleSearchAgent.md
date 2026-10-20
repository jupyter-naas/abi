# GoogleSearchAgent

## What it is
A thin `IntentAgent` wrapper plus a `create_agent()` factory that builds an agent configured to search the web via **Google Programmable Search Engine**, with additional tools to find **LinkedIn profile** and **LinkedIn organization** pages.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Creates and returns a configured `GoogleSearchAgent`.
  - Wires up:
    - Gemini chat model (`google_gemini_2_5_flash`)
    - Google Programmable Search Engine tools
    - LinkedIn search workflow tools (profile + organization)
    - Intent routing to the appropriate tool targets
  - Applies a system prompt that lists available tools.

- `class GoogleSearchAgent(IntentAgent)`
  - Concrete agent type returned by `create_agent()`.
  - No additional behavior beyond `IntentAgent` (empty subclass).

## Configuration/Dependencies
- **Module configuration** (read from `ABIModule.get_instance().configuration`):
  - `google_custom_search_api_key`
  - `google_custom_search_engine_id`

- **Tools/Workflows instantiated**
  - `GoogleProgrammableSearchEngineIntegrationConfiguration(api_key, search_engine_id)` via `as_tools(...)`
  - `SearchLinkedInProfilePageWorkflow(...).as_tools()`
  - `SearchLinkedInOrganizationPageWorkflow(...).as_tools()`

- **Model**
  - `naas_abi_marketplace.ai.gemini.models.google_gemini_2_5_flash.model`

- **Intent routing**
  - Web search intents target tool: `googlesearch_query`
  - LinkedIn profile search intents target tool: `googlesearch_search_linkedin_profile_page`
  - LinkedIn organization search intents target tool: `googlesearch_search_linkedin_organization_page`

## Usage
```python
from naas_abi_marketplace.applications.google_search.agents.GoogleSearchAgent import create_agent

agent = create_agent()

# Interact using the IntentAgent interface provided by naas_abi_core.
# (Exact call methods depend on IntentAgent implementation.)
```

## Caveats
- Requires valid `google_custom_search_api_key` and `google_custom_search_engine_id` in the `ABIModule` configuration; otherwise tool configuration will be incomplete.
- `GoogleSearchAgent` itself adds no new methods; all behavior comes from `IntentAgent` and the configured tools/intents.
