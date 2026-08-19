# LinkedInAgent

## What it is
An `IntentAgent` specialization that assembles LinkedIn + Google Search + SPARQL query tools into a single agent, with predefined intents for common LinkedIn-related requests.

## Public API
- `class LinkedInAgent(IntentAgent)`
  - Agent metadata:
    - `name = "LinkedIn"`
    - `description = "Access LinkedIn through your account."`
    - `avatar_url = "<linkedin bug svg url>"`
    - `system_prompt`: templated prompt with `[TOOLS]` and `[LINKEDIN_PROFILE_URL]` placeholders
    - `suggestions: list[str] = []`
  - `@classmethod New(cls, agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> LinkedInAgent`
    - Builds and returns a configured `LinkedInAgent` instance:
      - Loads default chat + embedding models from `ABIModule.get_instance().engine.services.model_registry`.
      - Creates tools from:
        - LinkedIn integration (`as_tools(LinkedInIntegrationConfiguration(...))`)
        - Google Search workflows (`SearchLinkedInProfilePageWorkflow`, `SearchLinkedInOrganizationPageWorkflow`)
        - Templatable SPARQL query tools (a fixed list of LinkedIn-related tool names)
      - Registers a fixed set of `Intent` routes (e.g., profile URL → `linkedin_get_profile_top_card`, organization URL → `linkedin_get_organization_info`, etc.).
      - Renders `system_prompt` by injecting tool descriptions and the configured LinkedIn profile URL.
      - Defaults:
        - `AgentConfiguration(system_prompt=...)` if not provided
        - `AgentSharedState(thread_id="0")` if not provided

## Configuration/Dependencies
This agent pulls configuration from several singleton modules:

- `naas_abi_marketplace.applications.linkedin.ABIModule`
  - `configuration.li_at`
  - `configuration.JSESSIONID`
  - `configuration.linkedin_profile_url`
- `naas_abi_marketplace.applications.google_search.ABIModule`
  - `configuration.google_custom_search_api_key`
  - `configuration.google_custom_search_engine_id`
- `naas_abi_marketplace.applications.naas.ABIModule`
  - `configuration.naas_api_key`
- `naas_abi_core.modules.templatablesparqlquery.ABIModule`
  - Used to load tools named:
    - `linkedin_search_connections_by_person_name`
    - `linkedin_count_connections_by_person`
    - `linkedin_get_connection_information`
    - `linkedin_search_email_address_by_person_uri`

Integrations/workflows used:
- `LinkedInIntegrationConfiguration` + `as_tools(...)`
- `NaasIntegrationConfiguration` (passed into LinkedIn integration)
- `GoogleProgrammableSearchEngineIntegrationConfiguration`
- `SearchLinkedInProfilePageWorkflow(...).as_tools()`
- `SearchLinkedInOrganizationPageWorkflow(...).as_tools()`

Model dependency:
- Requires `engine.services.model_registry` to be initialized (asserted in `New()`).

## Usage
```python
from naas_abi_marketplace.applications.linkedin.agents.LinkedInAgent import LinkedInAgent

agent = LinkedInAgent.New()

print(agent.name)         # "LinkedIn"
print(agent.description)  # "Access LinkedIn through your account."
```

## Caveats
- `New()` asserts `ModelRegistryService` is initialized (`registry is not None`).
- Requires valid LinkedIn auth cookies (`li_at`, `JSESSIONID`) and API credentials (Google Custom Search, Naas API key) to be set in their respective `ABIModule` configurations.
- The agent prompt instructs the agent to only work with valid LinkedIn URLs and to defer unsupported requests to `support@naas.ai`.
