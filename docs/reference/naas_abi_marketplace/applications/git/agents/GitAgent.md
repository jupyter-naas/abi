# GitAgent

## What it is
- `GitAgent` is an `Agent` configured to automate common Git/GitHub (via `gh`) workflows.
- It bundles a set of LangChain tools that run local `git` and `gh` CLI commands and can generate a PR description by invoking `PullRequestDescriptionAgent`.

## Public API
### Class: `GitAgent(Agent)`
- **Class attributes**
  - `name`: `"Git Agent"`
  - `description`: `"An agent to manage Git repositories"`
  - `system_prompt`: detailed operational rules for staging/committing/pushing and PR creation/update behavior.
  - `model`: `"gpt-5.2"` (note: actual chat model is retrieved from the model registry in `New()`)

### Constructor/Factory
- `@classmethod New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> GitAgent`
  - Creates and returns a configured `GitAgent`.
  - Retrieves the default chat model from `ABIModule.get_instance().engine.services.model_registry`.
  - Registers a set of tools (below) on the agent.
  - Defaults:
    - `agent_configuration`: `AgentConfiguration(system_prompt=GitAgent.system_prompt)`
    - `agent_shared_state`: `AgentSharedState(thread_id="0")`

### Tools exposed by the agent
These are registered as LangChain tools inside `New()`:

- `git_status() -> str`
  - Returns porcelain status (`git status --porcelain=v1 -b`) plus current branch.
- `git_diff_staged() -> str`
  - Returns staged diff (`git diff --staged`).
- `pull_request_description() -> str`
  - Invokes `PullRequestDescriptionAgent.New().invoke(...)` to generate PR description markdown.
- `git_log(limit: int = 10) -> str`
  - Returns recent commits (`git log -{limit} --oneline`).
- `git_add(paths: list[str]) -> str`
  - Stages only *tracked changes* among the provided paths; skips untracked/unchanged paths.
  - Uses `git status --porcelain -- <path>` to decide stage vs skip.
- `git_restore(paths: list[str]) -> str`
  - Restores working-tree files via `git checkout -- <paths>`.
- `git_commit(message: str) -> str`
  - Commits staged changes only.
  - If the branch exists on `origin`, runs `git pull origin <branch>` before committing.
  - Returns a message if nothing is staged (does not commit).
- `git_push() -> str`
  - Pushes current branch to origin, setting upstream (`git push -u origin <branch>`).
  - If branch exists on `origin`, runs `git pull origin <branch>` before pushing.
  - Falls back to `git push` if upstream is already set and `-u` push fails.
- `git_remote_branch_exists() -> str`
  - Returns `"true"`/`"false"` depending on whether `origin/<branch>` exists (via `git ls-remote`).
- `gh_pr_create(title: str, body: str, base: str = "main") -> str`
  - Creates a PR for the current branch using `gh pr create`; returns CLI output (typically URL).
- `gh_pr_find_for_branch() -> str`
  - Lists PRs for the current branch as JSON (`gh pr list --head <branch> --json ...`).
- `gh_pr_edit(number: int, title: str, body: str) -> str`
  - Edits an existing PR via `gh pr edit <number> --title ... --body ...`.
- `gh_pr_view() -> str`
  - Views the current PR as JSON (`gh pr view --json ...`).

## Configuration/Dependencies
- **Runtime dependencies**
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `langchain_core.tools.tool` for tool registration
  - `naas_abi_marketplace.applications.git.ABIModule` (used to access the model registry)
  - `naas_abi_marketplace.applications.git.agents.PullRequestDescriptionAgent` (used by `pull_request_description`)
- **External CLIs**
  - `git` must be available and run in a Git repository.
  - `gh` (GitHub CLI) must be installed and authenticated for PR operations.
- **Model**
  - The chat model used is fetched from the ModelRegistryService (`get_default_chat_model()`); an assertion fails if the registry is not initialized.

## Usage
Minimal example creating an agent and invoking it (the exact `Agent.invoke` behavior comes from `naas_abi_core`):

```python
from naas_abi_marketplace.applications.git.agents.GitAgent import GitAgent

agent = GitAgent.New()

# Example: ask for repo status (the agent may call the git_status tool)
print(agent.invoke("Show me the current branch and git status."))
```

## Caveats
- Tools execute real commands on the local machine (`subprocess`); they can modify the repository (commit/push/restore).
- `git_restore` uses `git checkout -- <paths>` (discarding working-tree changes for the given paths).
- `git_commit` and `git_push` may run `git pull origin <branch>` first when the remote branch exists; failures raise `RuntimeError` instructing to resolve conflicts.
- `git_add` intentionally **skips untracked files** and paths with no changes; it stages only tracked modifications among the provided paths.
- PR creation/update requires `gh` authentication and network access.
