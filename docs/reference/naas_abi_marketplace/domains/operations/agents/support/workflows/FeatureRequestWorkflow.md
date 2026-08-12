# FeatureRequestWorkflow

## What it is
A support workflow that:
- Creates a GitHub **feature request** issue via the GitHub REST integration.
- Adds the created issue to a GitHub Project via the GitHub GraphQL integration.
- Caches both REST and GraphQL responses as JSON in object storage.

## Public API
- **`FeatureRequestWorkflowConfiguration`** (`WorkflowConfiguration`)
  - Holds configuration for GitHub integrations and project/field IDs.
- **`FeatureRequestParameters`** (`WorkflowParameters`)
  - Input schema for creating a feature request issue (title, body, repo, labels, assignees, status/priority IDs).
- **`FeatureRequestWorkflow`** (`Workflow`)
  - **`create_feature_request(parameters: FeatureRequestParameters) -> Dict`**
    - Creates an issue, stores its JSON, adds it to a project with field values (status/priority/iteration), stores GraphQL JSON, and returns the created issue payload.
  - **`as_tools() -> List[BaseTool]`**
    - Exposes the workflow as a LangChain `StructuredTool` named `support_feature_request`.
  - **`as_api(...) -> None`**
    - Present but does nothing (returns `None`).

## Configuration/Dependencies
- Requires:
  - `GitHubIntegrationConfiguration` (REST API configuration)
  - `GitHubGraphqlIntegrationConfiguration` (GraphQL API configuration)
- Uses `ABIModule.get_instance().configuration` defaults for:
  - `data_store_path`
  - `project_node_id`
  - `status_field_id`
  - `priority_field_id`
  - `iteration_field_id`
  - `default_repository`
  - `priority_option_id`
  - `status_option_id`
- Persists JSON via `StorageUtils` using `ABIModule.get_instance().engine.services.object_storage`.

## Usage
```python
from naas_abi_marketplace.domains.support.workflows.FeatureRequestWorkflow import (
    FeatureRequestWorkflow,
    FeatureRequestWorkflowConfiguration,
    FeatureRequestParameters,
)
from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
    GitHubIntegrationConfiguration,
)
from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegrationConfiguration,
)

cfg = FeatureRequestWorkflowConfiguration(
    github_integration_config=GitHubIntegrationConfiguration(...),
    github_graphql_integration_config=GitHubGraphqlIntegrationConfiguration(...),
)

wf = FeatureRequestWorkflow(cfg)

issue = wf.create_feature_request(
    FeatureRequestParameters(
        issue_title="Add export button",
        issue_body="Please add a CSV export button to the dashboard.",
        # Optional overrides:
        # repo_name="owner/repo",
        # labels=["enhancement"],
        # assignees=["octocat"],
        # priority_id="...",
        # status_id="...",
    )
)

print(issue.get("html_url"))
```

## Caveats
- `as_api(...)` is a no-op; this workflow does not register any FastAPI routes.
- JSON caching path is derived from `issue["repository_url"]` by splitting on `https://api.github.com/repos/`; unexpected formats may affect storage paths.
- `assignees` default is `[]` even though it is typed as optional.
