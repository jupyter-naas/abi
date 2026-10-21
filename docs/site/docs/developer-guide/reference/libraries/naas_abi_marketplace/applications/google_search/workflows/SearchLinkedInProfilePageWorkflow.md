# SearchLinkedInProfilePageWorkflow

## What it is
A workflow that queries Google Programmable Search Engine for LinkedIn profile page URLs, extracts matching `/in/` profile links via regex, and persists each found profile page record as JSON in object storage.

## Public API
- **`SearchLinkedInProfilePageWorkflowConfiguration` (dataclass)**
  - Holds workflow configuration:
    - `integration_config`: `GoogleProgrammableSearchEngineIntegrationConfiguration`
    - `pattern`: regex used to validate/extract LinkedIn profile URLs (default: `r"https://.+\.linkedin\.[^/]+/in/[^?]+"`)
    - `datastore_path`: storage path for saved profile JSON files (defaults under `.../linkedin_profile_pages`)

- **`SearchLinkedInProfilePageWorkflowParameters` (pydantic)**
  - Execution parameters:
    - `profile_name` (str, required): profile name to search
    - `organization_name` (str, optional): organization name to include in query

- **`SearchLinkedInProfilePageWorkflow` (class)**
  - `__init__(configuration)`: builds the Google search integration and storage utility.
  - `search_linkedin_profile_page(parameters) -> list[dict]`:
    - Builds a search query from `profile_name` (+ optional `organization_name`) with `LinkedIn profile site:linkedin.com`
    - Calls the integration query
    - Filters results matching `configuration.pattern`
    - Extracts `profile_id` from the `/in/{profile_id}` URL segment
    - Persists each result as `{profile_id}.json` under `datastore_path/{profile_id}/`
    - Returns a list of page records with keys: `title`, `link`, `description`, `cse_image`
  - `as_tools() -> list[BaseTool]`:
    - Exposes the workflow as a LangChain `StructuredTool` named `googlesearch_search_linkedin_profile_page`
  - `as_api(...) -> None`:
    - Present but does not register any routes (no-op)

## Configuration/Dependencies
- **Integration**
  - `GoogleProgrammableSearchEngineIntegration` configured via `GoogleProgrammableSearchEngineIntegrationConfiguration`
- **Storage**
  - Uses `StorageUtils` backed by `ABIModule.get_instance().engine.services.object_storage`
  - Default `datastore_path` derives from `ABIModule.get_instance().configuration.datastore_path`

## Usage
```python
from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInProfilePageWorkflow import (
    SearchLinkedInProfilePageWorkflow,
    SearchLinkedInProfilePageWorkflowConfiguration,
    SearchLinkedInProfilePageWorkflowParameters,
)
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)

integration_config = GoogleProgrammableSearchEngineIntegrationConfiguration(
    # fill with required integration settings
)

wf = SearchLinkedInProfilePageWorkflow(
    SearchLinkedInProfilePageWorkflowConfiguration(integration_config=integration_config)
)

results = wf.search_linkedin_profile_page(
    SearchLinkedInProfilePageWorkflowParameters(
        profile_name="Ada Lovelace",
        organization_name="Example Corp",
    )
)

print(results)
```

## Caveats
- Only URLs matching the configured regex `pattern` are returned and saved.
- `as_api(...)` is a no-op; this workflow does not expose HTTP endpoints via FastAPI in its current implementation.
- Saving depends on `ABIModule` being initialized with a working object storage service and datastore path.
