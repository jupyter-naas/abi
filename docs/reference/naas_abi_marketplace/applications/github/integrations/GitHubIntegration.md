# GitHubIntegration

## What it is
- A small GitHub REST API client built on `requests`.
- Uses a personal access token via an `Authorization: Bearer ...` header.
- Includes `as_tools()` to expose selected operations as LangChain `StructuredTool` tools.

## Public API

### Configuration
- `@dataclass GitHubIntegrationConfiguration(access_token: str, base_url: str = "https://api.github.com", repositories: list[str] | None = None)`
  - Stores the GitHub personal access token and API base URL.
  - `repositories`: when set, requests reach only these repositories (`owner/repo`, case-insensitive); every other endpoint (users, organizations, other repositories) raises `ValueError`.
- `checked_endpoint(endpoint: str, repositories: list[str] | None = None) -> str`
  - What every request goes through: the endpoint is a path (query values go in `params`), each of its segments a plain name (`[A-Za-z0-9._-]+`, never `.` or `..`; so no `?` or `#` from a value), and, with `repositories`, it must lie under one of them. `ValueError` otherwise.
- `READ_TOOLS: frozenset[str]`: the names of the tools that only read; `GitHubAgent` carries these plus the write tools its module names.

### Client
- `class GitHubIntegration(configuration: GitHubIntegrationConfiguration)`
  - Initializes default headers:
    - `Authorization: Bearer <access_token>`
    - `Accept: application/vnd.github.v3+json`

#### Methods
- `_make_request(method, endpoint, data=None, params=None, headers=None) -> Any`
  - Internal request helper using `requests.request(...)`, `raise_for_status()`, and JSON decoding.

- `get_user_details(username: str) -> list | dict`
  - `GET /users/{username}`

- `create_user_repository(name: str, private: bool = False, description: str = "") -> list | dict`
  - `POST /user/repos`

- `get_repository_details(repo_name: str) -> list | dict`
  - `GET /repos/{owner}/{repo}` (`repo_name` is `owner/repo`)

- `list_organization_repositories(org: str, return_list: bool = False) -> list | dict`
  - `GET /orgs/{org}/repos` with params `page=1, per_page=100, sort=full_name`
  - If `return_list=True`, returns a derived list.

- `create_organization_repository(org: str, name: str, private: bool = True, description: str = "") -> list | dict`
  - `POST /orgs/{org}/repos`

- `update_organization_repository(org: str, repo_name: str, ..., accept: str = "application/vnd.github+json") -> list | dict`
  - `PATCH /repos/{org}/{repo_name}`
  - Builds payload from non-`None` keyword arguments.
  - Sends `Accept` header override.

- `delete_repository(repo_name: str, accept: str = "application/vnd.github+json") -> None`
  - `DELETE /repos/{repo_name}`

- `list_repository_activities(repo_name: str, ..., accept: str = "application/vnd.github+json") -> list | dict`
  - `GET /repos/{repo_name}/activity` with optional query params

- `get_repository_contributors(repo_name: str) -> list | dict`
  - `GET /repos/{repo_name}/contributors`

- `create_issue(repo_name: str, title: str, body: str, labels: list[str] | None = None, assignees: list[str] | None = None) -> dict`
  - `POST /repos/{repo_name}/issues`

- `get_issue(repo_name: str, issue_id: str) -> dict`
  - `GET /repos/{repo_name}/issues/{issue_id}`

- `list_issues(repo_name: str, ..., limit: int | None = -1, since: str | None = None, labels: str | None = None) -> list[dict]`
  - Paginates with `per_page=100` and increments `page` until empty result / non-list / limit reached.
  - Requests `GET /repos/{repo_name}/issues?{query_string}`

- `list_issue_comments(repo_name: str, ..., per_page: int = 30, page: int = 1) -> list | dict`
  - Requests `GET /repos/{repo_name}/issues/comments?{query_string}`

- `get_issue_comment(repo_name: str, comment_id: int, accept: str = "application/vnd.github+json") -> dict`
  - `GET /repos/{repo_name}/issues/comments/{comment_id}` with `Accept` override

- `update_issue_comment(repo_name: str, comment_id: int, body: str, accept: str = "application/vnd.github+json") -> dict`
  - `PATCH /repos/{repo_name}/issues/comments/{comment_id}` with `Accept` override

- `delete_issue_comment(repo_name: str, comment_id: int, accept: str = "application/vnd.github+json") -> None`
  - `DELETE /repos/{repo_name}/issues/comments/{comment_id}` with `Accept` override

- `create_issue_comment(repo_name: str, issue_number: int, body: str, accept: str = "application/vnd.github+json") -> dict`
  - `POST /repos/{repo_name}/issues/{issue_number}/comments` with `Accept` override

- `create_pull_request(repo_name: str, title: str, body: str, head: str, base: str) -> dict`
  - `POST /repos/{repo_name}/pulls`

- `list_pull_requests(repo_name: str, state: str = "open", sort: str = "created", direction: str = "desc", per_page: int = 30, page: int = 1) -> list`
  - `GET /repos/{repo_name}/pulls` with params

- `list_assignees(repo_name: str, per_page: int = 30, page: int = 1, accept: str = "application/vnd.github+json") -> list`
  - `GET /repos/{repo_name}/assignees` with params and `Accept` override

- `check_assignee(repo_name: str, assignee: str, accept: str = "application/vnd.github+json") -> bool`
  - Calls `GET /repos/{repo_name}/assignees/{assignee}` and returns `True` unless an `IntegrationConnectionError` is raised.

- `add_assignees_to_issue(repo_name: str, issue_number: int, assignees: list[str], accept: str = "application/vnd.github+json") -> dict`
  - `POST /repos/{repo_name}/issues/{issue_number}/assignees`

- `remove_assignees_from_issue(repo_name: str, issue_number: int, assignees: list[str], accept: str = "application/vnd.github+json") -> dict`
  - `DELETE /repos/{repo_name}/issues/{issue_number}/assignees`

- `check_assignee_permission(repo_name: str, issue_number: int, assignee: str, accept: str = "application/vnd.github+json") -> bool`
  - Calls `GET /repos/{repo_name}/issues/{issue_number}/assignees/{assignee}` and returns `True` unless an `IntegrationConnectionError` is raised.

- `get_repository_public_key(repo_name: str) -> dict`
  - `GET /repos/{repo_name}/actions/secrets/public-key`

- `list_repository_secrets(repo_name: str) -> list`
  - `GET /repos/{repo_name}/actions/secrets`

- `get_repository_secret(repo_name: str, secret_name: str) -> dict`
  - `GET /repos/{repo_name}/actions/secrets/{secret_name}`

- `create_or_update_repository_secret(repo_name: str, secret_name: str, value: str) -> dict`
  - Fetches repo public key, encrypts `value` using LibSodium sealed box, then:
  - `PUT /repos/{repo_name}/actions/secrets/{secret_name}`

- `delete_repository_secret(repo_name: str, secret_name: str) -> None`
  - `DELETE /repos/{repo_name}/actions/secrets/{secret_name}`

- `list_repository_contributors(repo_name: str, page: int = 1, per_page: int = 30, return_login: bool = False) -> list`
  - `GET /repos/{repo_name}/contributors` with pagination params.
  - If `return_login=True`, returns only `{"login", "contributions"}` for entries where `type == "User"`.

### Tool factory
- `as_tools(configuration: GitHubIntegrationConfiguration) -> list`
  - Returns a list of LangChain `StructuredTool` wrapping various methods on a `GitHubIntegration` instance.
  - No tool deletes a repository or writes or deletes an Actions secret: `delete_repository`, `create_or_update_repository_secret` and `delete_repository_secret` stay methods for code that calls them directly.
  - Defines Pydantic `BaseModel` schemas for tool arguments.

## Configuration/Dependencies
- Runtime dependencies:
  - `requests`
  - `naas_abi_core` (`logger`, `Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
  - `pydantic`
- Optional:
  - `langchain_core` (only for `as_tools`)
  - `PyNaCl` / `nacl` (only for `create_or_update_repository_secret`)

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
- `_make_request()` only catches `IntegrationConnectionError`; exceptions raised by `requests` (e.g., `requests.exceptions.HTTPError`) are not caught there.
- `list_organization_repositories(return_list=True)` returns a list of Python `set` objects (`{repo["name"], repo["full_name"]}`), not dictionaries.
- In `as_tools()`:
  - `github_update_organization_repository` passes a single `data` dict positionally into `update_organization_repository(...)`, but that method expects many keyword fields; this call signature does not match.
