# SearchLinkedInOrganizationPageWorkflow

## What it is
A workflow that uses **Google Programmable Search Engine** results to find and extract **LinkedIn organization page URLs** (company/school/showcase), then stores each matched page as JSON in object storage.

## Public API
- `SearchLinkedInOrganizationPageWorkflowConfiguration`
  - Workflow configuration:
    - `integration_config`: `GoogleProgrammableSearchEngineIntegrationConfiguration` used to query Google.
    - `pattern`: regex used to match LinkedIn organization URLs (default: `https://.+\.linkedin\.com/(company|school|showcase)/[^?]+`).
    - `datastore_path`: base storage path (defaults under `ABIModule.get_instance().configuration.datastore_path/linkedin_organization_pages`).

- `SearchLinkedInOrganizationPageWorkflowParameters`
  - Input parameters:
    - `organization_name: str`: organization name to search for.

- `SearchLinkedInOrganizationPageWorkflow`
  - `__init__(configuration)`
    - Instantiates Google search integration and storage utility.
  - `search_linkedin_organization_page(parameters) -> Any`
    - Builds query: `"{organization_name}+site:linkedin.com"` (spaces replaced by `+`).
    - Filters results by `configuration.pattern`.
    - Detects LinkedIn org type by URL path: `/company/`, `/school/`, `/showcase/`.
    - Extracts `organization_id` from the URL segment after the type.
    - Persists a JSON document per match via `StorageUtils.save_json(...)`.
    - Returns a list of dicts with keys:
      - `title`, `link`, `description`, `cse_image`.
  - `as_tools() -> list[BaseTool]`
    - Exposes a LangChain `StructuredTool` named `googlesearch_search_linkedin_organization_page`.
  - `as_api(...) -> None`
    - Present but does not register routes (returns `None`).

## Configuration/Dependencies
- Depends on:
  - `GoogleProgrammableSearchEngineIntegration` (requires `integration_config`).
  - `ABIModule.get_instance()` for datastore path and object storage service.
  - `StorageUtils` for persisting JSON outputs.
- Storage layout:
  - Saves under `datastore_path` with `"organization"` replaced by the detected type (`company`, `school`, or `showcase`), then `/<organization_id>/<organization_id>.json`.

## Usage
```python
from naas_abi_marketplace.applications.google_search.workflows.SearchLinkedInOrganizationPageWorkflow import (
    SearchLinkedInOrganizationPageWorkflow,
    SearchLinkedInOrganizationPageWorkflowConfiguration,
    SearchLinkedInOrganizationPageWorkflowParameters,
)
from naas_abi_marketplace.applications.google_search.integrations.GoogleProgrammableSearchEngineIntegration import (
    GoogleProgrammableSearchEngineIntegrationConfiguration,
)

config = SearchLinkedInOrganizationPageWorkflowConfiguration(
    integration_config=GoogleProgrammableSearchEngineIntegrationConfiguration(
        # provide required integration fields here
    )
)

wf = SearchLinkedInOrganizationPageWorkflow(config)
results = wf.search_linkedin_organization_page(
    SearchLinkedInOrganizationPageWorkflowParameters(organization_name="OpenAI")
)
print(results)
```

## Caveats
- Only URLs matching the configured regex and containing one of `/company/`, `/school/`, `/showcase/` are returned/saved.
- `as_api()` does not expose any HTTP endpoints.
