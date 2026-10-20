# LinkedInAgent

## What it is
A factory + thin agent class that assembles an `IntentAgent` configured to access LinkedIn data (via a LinkedIn integration), augment it with Google Search workflows, and expose a set of predefined intents for common LinkedIn-related requests.

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> IntentAgent`
  - Builds and returns a configured `LinkedInAgent` instance:
    - Loads LinkedIn + Google Search + Naas configuration from their respective `ABIModule` singletons.
    - Creates tool sets from:
      - LinkedIn integration tools (`as_tools(...)`)
      - Google Search workflows (profile/org page search)
      - SPARQL templated query tools (a fixed set of LinkedIn-related query tools)
    - Registers a list of `Intent` mappings to route common user requests to specific tools.
    - Renders the `SYSTEM_PROMPT` by injecting tool descriptions and the user LinkedIn profile URL.
    - Applies default `AgentConfiguration(system_prompt=...)` and `AgentSharedState(thread_id="0")` when not provided.

- `class LinkedInAgent(IntentAgent)`
  - No additional behavior; inherits everything from `IntentAgent`.

## Configuration/Dependencies
This agent relies on several modules being configured and available via `get_instance()`:

- `naas_abi_marketplace.applications.linkedin.ABIModule`
  - `configuration.li_at`
  - `configuration.JSESSIONID`
  - `configuration.linkedin_profile_url`

- `naas_abi_marketplace.applications.google_search.ABIModule`
  - `configuration.google_custom_search_api_key`
  - `configuration.google_custom_search_engine_id`

- `naas_abi_marketplace.applications.naas.ABIModule`
  - `configuration.naas_api_key`

Tools/workflows/integrations used:
- `naas_abi_marketplace.applications.linkedin.integrations.LinkedInIntegration`
  - `LinkedInIntegrationConfiguration`, `as_tools(...)`
- `naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration`
  - `GoogleProgrammableSearchEngineIntegrationConfiguration`
- `naas_abi_marketplace.applications.google_search.workflows.*`
  - `SearchLinkedInProfilePageWorkflow`
  - `SearchLinkedInOrganizationPageWorkflow`
- `naas_abi_core.modules.templatablesparqlquery.ABIModule`
  - Adds tools for:
    - `linkedin_search_connections_by_person_name`
    - `linkedin_count_connections_by_person`
    - `linkedin_get_connection_information`
    - `linkedin_search_email_address_by_person_uri`

Model dependency:
- `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`

## Usage
```python
from naas_abi_marketplace.applications.linkedin.agents.LinkedInAgent import create_agent

agent = create_agent()

# The returned object is an IntentAgent configured with tools/intents/system prompt.
# How you run/chat with the agent depends on the IntentAgent interface in naas_abi_core.
print(agent.name)  # "LinkedIn"
```

## Caveats
- Requires valid configuration values to be present in the referenced `ABIModule` instances (LinkedIn auth cookies, Google Search API credentials, Naas API key).
- The `LinkedInAgent` class itself adds no behavior; all behavior comes from `IntentAgent`, configured tools, and intents.
- The system prompt enforces working only with valid LinkedIn URLs and instructs to defer unsupported requests to `support@naas.ai`.
