# SearchLinkedInProfilePageWorkflow

## What it is
A workflow that uses Google Programmable Search Engine to find LinkedIn `/in/` profile page URLs for a given name (optionally scoped by organization), extracts matching links via regex, and saves each found profile page record as JSON in object storage.

## Public API
- **`SearchLinkedInProfilePageWorkflowConfiguration` (dataclass, `WorkflowConfiguration`)**
  - Holds workflow configuration:
    - `integration_config`: `GoogleProgrammableSearchEngineIntegrationConfiguration` (required)
    - `pattern`: regex used to match LinkedIn profile URLs (default: `r"https://.+\.linkedin\.[^/]+/in/[^?]+"`)
    - `datastore_path`: base path where profile JSON files are saved (defaults to `<ABIModule datastore_path>/linkedin_profile_pages`)

- **`SearchLinkedInProfilePageWorkflowParameters` (`WorkflowParameters`)**
  - Execution parameters:
    - `profile_name` (str, required): name to search for
    - `organization_name` (str, optional): organization to include in the query

- **`SearchLinkedInProfilePageWorkflow` (`Workflow`)**
  - `__init__(configuration)`: initializes the Google search integration and `StorageUtils`.
  - `search_linkedin_profile_page(parameters) -> list[dict]`:
    - Builds a Google query from `profile_name` and optional `organization_name`
    - Calls `GoogleProgrammableSearchEngineIntegration.query(query)`
    - Filters results whose `link` matches `configuration.pattern`
    - Extracts `profile_id` from the URL segment after `/in/`
    - Saves a JSON file at: `datastore_path/<profile_id>/<profile_id>.json`
    - Returns a list of dicts: `title`, `link`, `description`, `cse_image`
  - `as_tools() -> list[BaseTool]`:
    - Exposes a LangChain `StructuredTool` named `googlesearch_search_linkedin_profile_page`.
  - `as_api(router, ...) -> None`:
    - Present but does not register routes (no implementation beyond defaulting `tags`).

## Configuration/Dependencies
- **Google search integration**
  - `GoogleProgrammableSearchEngineIntegration` configured by `GoogleProgrammableSearchEngineIntegrationConfiguration`.
- **Object storage**
  - Uses `StorageUtils` backed by `ABIModule.get_instance().engine.services.object_storage`.
  - Default `datastore_path` uses `ABIModule.get_instance().configuration.datastore_path`.

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
    # provide required integration settings
)

workflow = SearchLinkedInProfilePageWorkflow(
    SearchLinkedInProfilePageWorkflowConfiguration(integration_config=integration_config)
)

pages = workflow.search_linkedin_profile_page(
    SearchLinkedInProfilePageWorkflowParameters(
        profile_name="Ada Lovelace",
        organization_name="Example Corp",
    )
)

print(pages)
```

## Caveats
- Only results whose URL matches `configuration.pattern` are returned/saved.
- `profile_id` is parsed from the URL using `url.split("/in/")[-1]...`; unexpected LinkedIn URL formats may not parse as intended.
- Persistence requires `ABIModule` to be initialized with a working object storage service and configured `datastore_path`.
- `as_api(...)` does not currently expose any HTTP endpoints.
