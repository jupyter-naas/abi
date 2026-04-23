# ReportBugWorkflow

## What it is
A workflow that creates a GitHub bug report issue (via REST) and then adds that issue to a GitHub Project (via GraphQL). It also caches the REST and GraphQL responses as JSON in an object-storage-backed datastore.

## Public API

- `ReportBugWorkflowConfiguration(WorkflowConfiguration)`
  - Holds configuration required to talk to GitHub (REST + GraphQL) and to target a specific GitHub Project and its fields.
- `ReportBugParameters(WorkflowParameters)`
  - Input schema for creating a bug report issue and setting project fields.
- `ReportBugWorkflow(Workflow)`
  - `report_bug(parameters: ReportBugParameters) -> Dict`
    - Creates the GitHub issue, stores it to the datastore, adds it to the configured project with field values, stores the GraphQL response, and returns the created issue dict.
  - `as_tools() -> List[BaseTool]`
    - Exposes the workflow as a LangChain `StructuredTool` named `support_bug_report`.
  - `as_api(...) -> None`
    - Present but does nothing (returns `None` and does not register routes).

## Configuration/Dependencies

### Configuration fields
`ReportBugWorkflowConfiguration` requires:
- `github_integration_config: GitHubIntegrationConfiguration` (GitHub REST)
- `github_graphql_integration_config: GitHubGraphqlIntegrationConfiguration` (GitHub GraphQL)

It also uses defaults from `ABIModule.get_instance().configuration`:
- `data_store_path`
- `project_node_id`
- `status_field_id`
- `priority_field_id`
- `iteration_field_id`

### Runtime dependencies
- GitHub integrations:
  - `GitHubIntegration.create_issue(...)`
  - `GitHubGraphqlIntegration.get_current_iteration_id(project_node_id)`
  - `GitHubGraphqlIntegration.add_issue_to_project(...)`
- Storage:
  - `StorageUtils.save_json(data, path, filename)` backed by `ABIModule.get_instance().engine.services.object_storage`

### Cached files written
- REST issue response:
  - `<data_store_path>/<org>/<repo>/issues/<issue_number>.json` (path derived from `issue["repository_url"]`)
- GraphQL response:
  - `<data_store_path>/<org>/<repo>/issues/<issue_number>_graphql.json`

## Usage

```python
from naas_abi_marketplace.domains.support.workflows.ReportBugWorkflow import (
    ReportBugWorkflow,
    ReportBugWorkflowConfiguration,
    ReportBugParameters,
)
from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
    GitHubIntegrationConfiguration,
)
from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegrationConfiguration,
)

cfg = ReportBugWorkflowConfiguration(
    github_integration_config=GitHubIntegrationConfiguration(...),
    github_graphql_integration_config=GitHubGraphqlIntegrationConfiguration(...),
)

wf = ReportBugWorkflow(cfg)

issue = wf.report_bug(
    ReportBugParameters(
        issue_title="Crash when clicking Save",
        issue_body="Steps to reproduce:\n1. ...\n2. ...\nExpected: ...\nActual: ...",
        # repo_name, labels, priority_id, status_id may use ABIModule defaults
    )
)

print(issue.get("html_url") or issue.get("url"))
```

Using as a LangChain tool:
```python
tool = ReportBugWorkflow(cfg).as_tools()[0]
result = tool.run({
    "issue_title": "UI freeze on dashboard",
    "issue_body": "Repro steps: ...",
})
```

## Caveats
- `as_api(...)` is a no-op; it does not register any FastAPI routes.
- `assignees` defaults to an empty list (`[]`) at the class level; it is passed through to `create_issue`.
- The cache path is derived by splitting `issue["repository_url"]` on `"https://api.github.com/repos/"`; if the returned URL format differs, the derived path may be incorrect.
