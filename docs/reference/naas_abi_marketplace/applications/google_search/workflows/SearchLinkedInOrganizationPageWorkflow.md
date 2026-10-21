# SearchLinkedInOrganizationPageWorkflow

## What it is
A workflow that queries Google Programmable Search Engine for an organization name, filters results to LinkedIn organization pages (`company`, `school`, `showcase`), saves matched pages as JSON to object storage, and returns the matched page metadata.

## Public API
- `SearchLinkedInOrganizationPageWorkflowConfiguration` (dataclass)
  - Purpose: Configure integration, matching pattern, and storage path.
  - Fields:
    - `integration_config: GoogleProgrammableSearchEngineIntegrationConfiguration` — Google PSE integration config.
    - `pattern: str` — regex used to match LinkedIn org URLs (default: `r"https://.+\.linkedin\.com/(company|school|showcase)/[^?]+"`).
    - `datastore_path: str` — base path for saving results (default: `<ABIModule datastore_path>/linkedin_organization_pages`).

- `SearchLinkedInOrganizationPageWorkflowParameters` (Pydantic/WorkflowParameters)
  - Purpose: Input parameters for execution.
  - Fields:
    - `organization_name: str` — organization name to search for.

- `SearchLinkedInOrganizationPageWorkflow` (Workflow)
  - `__init__(configuration: SearchLinkedInOrganizationPageWorkflowConfiguration)`
    - Purpose: Instantiate the Google search integration and storage utility.
  - `search_linkedin_organization_page(parameters: SearchLinkedInOrganizationPageWorkflowParameters) -> Any`
    - Purpose: Search for LinkedIn organization pages and persist each match as JSON.
    - Behavior:
      - Query: `"{organization_name_with_+}+site:linkedin.com"`.
      - For each result whose `link` matches `configuration.pattern`:
        - Detect org type by URL containing `/company/`, `/school/`, or `/showcase/`.
        - Extract `organization_id` from the URL segment after the org type.
        - Build `page_data` with:
          - `title` (from result)
          - `link` (result URL)
          - `description` (from `pagemap.metatags[0]["og:description"]` else `snippet`)
          - `cse_image` (from `pagemap.cse_image[0]["src"]` else `None`)
        - Save JSON to:  
          `configuration.datastore_path` with `"organization"` replaced by the detected type, then `/<organization_id>/<organization_id>.json`.
      - Returns: `list[dict]` of `page_data`.
  - `as_tools() -> list[BaseTool]`
    - Purpose: Expose a LangChain `StructuredTool` named `googlesearch_search_linkedin_organization_page`.
  - `as_api(...) -> None`
    - Purpose: API wiring stub; does not add routes in the shown code.

## Configuration/Dependencies
- Dependencies:
  - `GoogleProgrammableSearchEngineIntegration` (uses `integration_config`; called via `.query(query)`).
  - `ABIModule.get_instance()`:
    - `configuration.datastore_path` used for default `datastore_path`.
    - `engine.services.object_storage` used by `StorageUtils`.
  - `StorageUtils.save_json(...)` writes matched page data to object storage.
- URL matching:
  - Regex: `SearchLinkedInOrganizationPageWorkflowConfiguration.pattern`
  - Org type detection is based on substring presence in the URL (`/company/`, `/school/`, `/showcase/`).

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

cfg = SearchLinkedInOrganizationPageWorkflowConfiguration(
    integration_config=GoogleProgrammableSearchEngineIntegrationConfiguration(
        # fill required integration fields
    )
)

wf = SearchLinkedInOrganizationPageWorkflow(cfg)
out = wf.search_linkedin_organization_page(
    SearchLinkedInOrganizationPageWorkflowParameters(organization_name="OpenAI")
)
print(out)
```

## Caveats
- Only results whose URL matches the regex **and** includes one of `/company/`, `/school/`, or `/showcase/` are saved/returned.
- Storage path uses `datastore_path.replace("organization", organization_type)`; ensure your base path naming aligns with this replacement behavior.
- `as_api()` is incomplete in the provided code and does not register endpoints.
