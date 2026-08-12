# GitHubGraphqlIntegration

## What it is
A small integration wrapper around the GitHub GraphQL API that:
- Executes GraphQL queries/mutations using a GitHub personal access token.
- Provides helper methods for GitHub Projects (ProjectV2), project fields, and project items.
- Optionally exposes a few methods as LangChain `StructuredTool`s.

## Public API

### `GitHubGraphqlIntegrationConfiguration`
Dataclass configuration for the integration:
- `access_token: str` — GitHub personal access token.
- `api_url: str = "https://api.github.com/graphql"` — GitHub GraphQL endpoint.

### `GitHubGraphqlIntegration`
Integration client.

- `execute_query(query: str, variables: dict | None = None) -> dict[str, Any]`
  - Posts a GraphQL request to `api_url`.
  - Returns parsed JSON.
  - If the response JSON contains `"errors"`, logs and returns `{"error": result["errors"]}`.

- `get_project_node_id(organization: str, number: int) -> dict[str, Any]`
  - Fetches the node ID of an organization ProjectV2 by project number.

- `get_project_details(project_node_id: str) -> dict[str, Any]`
  - Fetches ProjectV2 details including:
    - `title`, `number`, `url`, `shortDescription`, `public`, `closed`
    - items total count
    - up to first 20 fields (basic fields, iteration fields with iteration config, single-select fields with options)

- `get_current_iteration_id(project_node_id: str) -> str | None`
  - Finds the iteration whose `[startDate, startDate + duration]` contains the current UTC time.
  - Returns iteration `id` or `None` if no iteration field / match is found.

- `list_priorities(project_node_id: str) -> list[dict[str, Any]]`
  - Returns the `options` list for the project field named `"Priority"`, or `[]` if missing.

- `get_project_fields(project_id: str) -> dict[str, Any]`
  - Fetches up to first 20 project fields (regular fields, iteration fields with iteration ids and start dates, single-select fields with options).

- `get_item_id_from_node_id(node_id: str) -> dict[str, Any]`
  - For an Issue or Pull Request node ID, fetches the first associated project item (if any), including its project metadata.

- `get_item_details(item_id: str) -> dict[str, Any]`
  - Fetches ProjectV2Item details and up to 20 field values:
    - text, date, single-select, number, iteration, milestone.

- `add_issue_to_project(...) -> dict[str, Any]`
  - Adds an issue to a project via `addProjectV2ItemById`.
  - Optionally updates:
    - status single-select field (`singleSelectOptionId`)
    - priority single-select field (`singleSelectOptionId`)
    - iteration field (`iterationId`)
  - Returns:
    - `{"add_result": ..., "status_result": ..., "priority_result": ..., "iteration_result": ...}`
    - Optional results are `None` when not executed.

### `as_tools(configuration: GitHubGraphqlIntegrationConfiguration) -> list`
Returns LangChain `StructuredTool` instances wrapping:
- `githubgraphql_get_project_node_id`
- `githubgraphql_get_project_details`
- `githubgraphql_list_priorities`

## Configuration/Dependencies

- Required:
  - `requests`
  - `naas_abi_core` (`logger`, `Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- Optional (only for `as_tools`):
  - `langchain_core.tools.StructuredTool`
  - `pydantic`
- Authentication:
  - Uses header `Authorization: Bearer <access_token>`
  - Uses `Content-Type: application/json`

## Usage

### Basic usage
```python
from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegration,
    GitHubGraphqlIntegrationConfiguration,
)

cfg = GitHubGraphqlIntegrationConfiguration(access_token="YOUR_GITHUB_TOKEN")
gh = GitHubGraphqlIntegration(cfg)

res = gh.get_project_node_id("my-org", 1)
project_id = res["data"]["organization"]["projectV2"]["id"]

priorities = gh.list_priorities(project_id)
print(priorities)
```

### Add an issue to a project (optionally set fields)
```python
result = gh.add_issue_to_project(
    project_node_id="PROJECT_NODE_ID",
    issue_node_id="ISSUE_NODE_ID",
    status_field_id="STATUS_FIELD_ID",
    status_option_id="STATUS_OPTION_ID",
)
print(result["add_result"])
```

## Caveats
- `execute_query()` calls `response.raise_for_status()`; HTTP errors from `requests` may propagate (it only catches `IntegrationConnectionError`).
- Several methods index into `result["data"]...`; if `execute_query()` returns `{"error": ...}`, callers may raise `KeyError`.
- `get_current_iteration_id()` expects `startDate` in `%Y-%m-%d` and compares against `datetime.now(UTC)`.
