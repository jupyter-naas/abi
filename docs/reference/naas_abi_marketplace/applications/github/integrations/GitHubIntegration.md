# GitHubIntegration

## What it is
- A lightweight GitHub REST API client built on `requests`, using a personal access token for authentication.
- Includes a helper `as_tools()` to expose selected operations as LangChain `StructuredTool` tools.

## Public API

### Configuration
- `GitHubIntegrationConfiguration(access_token: str, base_url: str = "https://api.github.com")`
  - Holds auth token and API base URL.

### Client
- `class GitHubIntegration(configuration: GitHubIntegrationConfiguration)`
  - Initializes default request headers:
    - `Authorization: Bearer <token>`
    - `Accept: application/vnd.github.v3+json`

#### Methods
- `get_user_details(username: str) -> List | Dict`
  - Fetch GitHub user details (`GET /users/{username}`).

- `create_user_repository(name: str, private: bool = False, description: str = "") -> List | Dict`
  - Create a repo for the authenticated user (`POST /user/repos`).

- `get_repository_details(repo_name: str) -> List | Dict`
  - Fetch repository details (`GET /repos/{owner}/{repo}`).

- `list_organization_repositories(org: str, return_list: bool = False) -> List | Dict`
  - List repos in an org (`GET /orgs/{org}/repos`).
  - If `return_list=True`, returns a derived list from the API response.

- `create_organization_repository(org: str, name: str, private: bool = True, description: str = "") -> List | Dict`
  - Create an org repo (`POST /orgs/{org}/repos`).

- `update_organization_repository(..., accept: str = "application/vnd.github+json") -> List | Dict`
  - Patch repo settings (`PATCH /repos/{org}/{repo_name}`) using only provided (non-`None`) fields.
  - Sends `Accept` header override.

- `delete_repository(repo_name: str, accept: str = "application/vnd.github+json") -> None`
  - Delete a repository (`DELETE /repos/{repo_name}`).

- `list_repository_activities(..., accept: str = "application/vnd.github+json") -> List | Dict`
  - List repository activity (`GET /repos/{repo_name}/activity`) with optional filters.

- `get_repository_contributors(repo_name: str) -> List | Dict`
  - Get contributors (`GET /repos/{repo_name}/contributors`).

- `create_issue(repo_name: str, title: str, body: str, labels: Optional[List[str]] = [], assignees: Optional[List[str]] = []) -> Dict`
  - Create an issue (`POST /repos/{repo_name}/issues`).

- `get_issue(repo_name: str, issue_id: str) -> Dict`
  - Get an issue (`GET /repos/{repo_name}/issues/{issue_id}`).

- `list_issues(..., limit: Optional[int] = -1, since: Optional[str] = None, labels: Optional[str] = None) -> List[Dict]`
  - Paginated issue listing using `per_page=100` and a `page` loop.
  - Stops when:
    - response is not a list, or
    - response is empty, or
    - `limit` reached (if not `-1`).

- `list_issue_comments(..., per_page: int = 30, page: int = 1) -> List | Dict`
  - List issue/PR comments (`GET /repos/{repo_name}/issues/comments`) with query-string params.

- `get_issue_comment(repo_name: str, comment_id: int, accept: str = "application/vnd.github+json") -> Dict`
  - Get a single issue comment with `Accept` override.

- `update_issue_comment(repo_name: str, comment_id: int, body: str, accept: str = "application/vnd.github+json") -> Dict`
  - Update a comment (`PATCH /repos/{repo_name}/issues/comments/{comment_id}`).

- `delete_issue_comment(repo_name: str, comment_id: int, accept: str = "application/vnd.github+json") -> None`
  - Delete a comment (`DELETE /repos/{repo_name}/issues/comments/{comment_id}`).

- `create_issue_comment(repo_name: str, issue_number: int, body: str, accept: str = "application/vnd.github+json") -> Dict`
  - Create an issue comment (`POST /repos/{repo_name}/issues/{issue_number}/comments`).

- `create_pull_request(repo_name: str, title: str, body: str, head: str, base: str) -> Dict`
  - Create a pull request (`POST /repos/{repo_name}/pulls`).

- `list_pull_requests(repo_name: str, state: str = "open", sort: str = "created", direction: str = "desc", per_page: int = 30, page: int = 1) -> List`
  - List pull requests (`GET /repos/{repo_name}/pulls`).

- `list_assignees(repo_name: str, per_page: int = 30, page: int = 1, accept: str = "application/vnd.github+json") -> List`
  - List available assignees (`GET /repos/{repo_name}/assignees`).

- `check_assignee(repo_name: str, assignee: str, accept: str = "application/vnd.github+json") -> bool`
  - Attempts to fetch assignability (`GET /repos/{repo_name}/assignees/{assignee}`) and returns `True` unless an `IntegrationConnectionError` is raised.

- `add_assignees_to_issue(repo_name: str, issue_number: int, assignees: List[str], accept: str = "application/vnd.github+json") -> Dict`
  - Add assignees (`POST /repos/{repo_name}/issues/{issue_number}/assignees`).

- `remove_assignees_from_issue(repo_name: str, issue_number: int, assignees: List[str], accept: str = "application/vnd.github+json") -> Dict`
  - Remove assignees (`DELETE /repos/{repo_name}/issues/{issue_number}/assignees`).

- `check_assignee_permission(repo_name: str, issue_number: int, assignee: str, accept: str = "application/vnd.github+json") -> bool`
  - Checks assignability for a specific issue by requesting:
    - `GET /repos/{repo_name}/issues/{issue_number}/assignees/{assignee}`

- `get_repository_public_key(repo_name: str) -> Dict`
  - Get repo Actions secrets public key (`GET /repos/{repo_name}/actions/secrets/public-key`).

- `list_repository_secrets(repo_name: str) -> List`
  - List repo secrets metadata (`GET /repos/{repo_name}/actions/secrets`).

- `get_repository_secret(repo_name: str, secret_name: str) -> Dict`
  - Get secret metadata (`GET /repos/{repo_name}/actions/secrets/{secret_name}`).

- `create_or_update_repository_secret(repo_name: str, secret_name: str, value: str) -> Dict`
  - Encrypts `value` using the repository public key (LibSodium sealed box) and stores it:
    - `PUT /repos/{repo_name}/actions/secrets/{secret_name}`

- `delete_repository_secret(repo_name: str, secret_name: str) -> None`
  - Delete a secret (`DELETE /repos/{repo_name}/actions/secrets/{secret_name}`).

- `list_repository_contributors(repo_name: str, page: int = 1, per_page: int = 30, return_login: bool = False) -> List`
  - Lists contributors with pagination.
  - If `return_login=True`, returns a filtered list of `{"login", "contributions"}` for entries where `type == "User"`.

### Tool factory
- `as_tools(configuration: GitHubIntegrationConfiguration) -> list`
  - Returns a list of LangChain `StructuredTool` instances wrapping selected methods on a `GitHubIntegration` instance.

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core` (logger + `Integration` base classes)
  - `pydantic`
- Optional (only for `create_or_update_repository_secret`):
  - `PyNaCl` (`nacl`)
- Optional (only for `as_tools`):
  - `langchain_core.tools.StructuredTool`

## Usage

```python
from naas_abi_marketplace.applications.github.integrations.GitHubIntegration import (
    GitHubIntegration,
    GitHubIntegrationConfiguration,
)

cfg = GitHubIntegrationConfiguration(access_token="YOUR_GITHUB_TOKEN")
gh = GitHubIntegration(cfg)

repo = gh.get_repository_details("octocat/Hello-World")
print(repo.get("full_name"))

issues = gh.list_issues("octocat/Hello-World", limit=5)
print(len(issues))
```

## Caveats
- `_make_request()` catches `IntegrationConnectionError`, but `requests` typically raises `requests.exceptions.RequestException`/`HTTPError`; these are not explicitly handled here.
- `create_issue()` uses mutable default arguments (`labels=[]`, `assignees=[]`).
- `list_organization_repositories(return_list=True)` builds items with `{repo["name"], repo["full_name"]}` (a Python `set`, not a dict).
- In `as_tools()`:
  - `github_update_organization_repository` passes a single `data` dict into `update_organization_repository()` where the method signature expects many keyword parameters.
  - `github_delete_organization_repository` calls `integration.delete_repository(org, repo_name)` but `delete_repository()` accepts only `repo_name` (plus `accept`).
- `list_issues()` and `list_issue_comments()` construct query strings manually and include them in the endpoint string instead of passing `params`.
