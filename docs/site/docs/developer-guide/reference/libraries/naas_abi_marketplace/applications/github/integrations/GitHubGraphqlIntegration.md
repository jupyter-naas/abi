# GitHubGraphqlIntegration

## What it is
A small integration wrapper around the GitHub GraphQL API that:
- Executes GraphQL queries/mutations using a GitHub personal access token.
- Provides convenience methods for GitHub Projects (ProjectV2) and Project items.
- Optionally exposes a subset of methods as LangChain `StructuredTool`s.

## Public API

### Configuration
- `GitHubGraphqlIntegrationConfiguration`
  - `access_token: str` — GitHub personal access token (Bearer token).
  - `api_url: str = "https://api.github.com/graphql"` — GraphQL endpoint.

### Integration class
- `GitHubGraphqlIntegration(configuration)`
  - `execute_query(query: str, variables: Optional[Dict] = None) -> Dict[str, Any]`  
    Post a GraphQL request to `api_url`. Returns parsed JSON. If the response JSON contains `"errors"`, returns `{"error": ...}`.
  - `get_project_node_id(organization: str, number: int) -> Dict[str, Any]`  
    Fetch a ProjectV2 node ID for an organization project number.
  - `get_project_details(project_node_id: str) -> Dict[str, Any]`  
    Fetch ProjectV2 details (title, url, visibility/closed flags, items count, and first 20 fields including iteration/single-select configs).
  - `get_current_iteration_id(project_node_id: str) -> str | None`  
    From project details, finds the iteration whose date window includes `datetime.now()`. Returns iteration id or `None`.
  - `list_priorities(project_node_id: str) -> List[Dict[str, Any]]`  
    Returns `options` from the field named `"Priority"`, or `[]` if not found.
  - `get_project_fields(project_id: str) -> Dict[str, Any]`  
    Fetch first 20 project fields (basic fields, iteration fields with iteration IDs/start dates, and single-select fields with options).
  - `get_item_id_from_node_id(node_id: str) -> Dict[str, Any]`  
    For an Issue or Pull Request node ID, returns the first associated project item (if any) and its project info.
  - `get_item_details(item_id: str) -> Dict[str, Any]`  
    Fetch ProjectV2Item details and up to 20 field values (text/date/single-select/number/iteration/milestone).
  - `add_issue_to_project(...) -> Dict[str, Any]`  
    Adds an issue to a project (`addProjectV2ItemById`), then optionally updates:
    - a status single-select field
    - a priority single-select field
    - an iteration field  
    Returns a dict with `add_result`, and optional `status_result`/`priority_result`/`iteration_result` (may be `None`).

### Tool factory
- `as_tools(configuration: GitHubGraphqlIntegrationConfiguration) -> list`
  - Returns LangChain `StructuredTool` instances for:
    - `githubgraphql_get_project_node_id`
    - `githubgraphql_get_project_details`
    - `githubgraphql_list_priorities`

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core` (for `logger` and `Integration` base classes)
- Optional (only if using `as_tools`):
  - `langchain_core.tools.StructuredTool`
  - `pydantic`
- Authentication:
  - Uses HTTP header `Authorization: Bearer <access_token>`.

## Usage

### Basic usage
```python
from naas_abi_marketplace.applications.github.integrations.GitHubGraphqlIntegration import (
    GitHubGraphqlIntegration,
    GitHubGraphqlIntegrationConfiguration,
)

cfg = GitHubGraphqlIntegrationConfiguration(access_token="YOUR_GITHUB_TOKEN")
gh = GitHubGraphqlIntegration(cfg)

# Get a project node id
res = gh.get_project_node_id("my-org", 1)
project_id = res["data"]["organization"]["projectV2"]["id"]

# List priorities configured in the project
priorities = gh.list_priorities(project_id)
print(priorities)
```

### Add an issue to a project (and optionally set fields)
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
- `execute_query` calls `response.raise_for_status()`, which raises `requests` exceptions; the method only catches `IntegrationConnectionError`, so HTTP errors may propagate instead of returning `{"error": ...}`.
- Several methods assume a successful GraphQL response shape (e.g., `project_details["data"]["node"]...`). If `execute_query` returns `{"error": ...}`, these methods may raise `KeyError`.
- `get_current_iteration_id` depends on iteration `startDate` being in `%Y-%m-%d` format and uses the local system time (`datetime.now()`).
