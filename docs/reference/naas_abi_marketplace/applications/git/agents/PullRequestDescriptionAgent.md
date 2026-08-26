# PullRequestDescriptionAgent

## What it is
- An `Agent` implementation that generates a GitHub pull request description from the current git branch and diff against `origin/main...HEAD`.
- Exposes two tools to:
  - fetch branch name + diff (`git_diff`)
  - store the generated description (`store_pull_request_description`) to object storage as `git/pull_request_description.md`.

## Public API
- `class PullRequestDescriptionAgent(Agent)`
  - Agent metadata:
    - `name = "Pull Request Description Agent"`
    - `description = "A agent to generate a description for a pull request"`
    - `system_prompt`: instructs the agent to call `git_diff`, write a markdown PR description, then call `store_pull_request_description`.
    - `model = "gpt-5.2"` (attribute defined on the class; runtime model is taken from the model registry in `New()`).
- `PullRequestDescriptionAgent.New(agent_shared_state: AgentSharedState | None = None, agent_configuration: AgentConfiguration | None = None) -> PullRequestDescriptionAgent`
  - Factory that:
    - Retrieves the application module (`ABIModule`) and its services:
      - `engine.services.object_storage` (for persistence)
      - `engine.services.model_registry.get_default_chat_model()` (chat model)
    - Registers two LangChain tools:
      - `git_diff() -> str`: returns `"Branch name: <branch>\n\n<diff>"`
      - `store_pull_request_description(description: str | None = None) -> str`: stores content or returns a recoverable error message if `description` is missing/empty
    - Returns a configured `PullRequestDescriptionAgent` instance with:
      - `tools=[git_diff, store_pull_request_description]`
      - default `AgentSharedState(thread_id="0")` if not provided
      - default `AgentConfiguration(system_prompt=cls.system_prompt)` if not provided

## Configuration/Dependencies
- Dependencies:
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - `langchain_core.tools.tool` (tool decorator)
  - `naas_abi_marketplace.applications.git.ABIModule` (module singleton and services)
  - External `git` CLI (invoked via `subprocess.check_output`)
- Git commands executed by `git_diff`:
  - `git branch --show-current`
  - `git diff origin/main...HEAD -- . :!uv.lock` (excludes `uv.lock`)
- Storage:
  - Uses `object_storage.put_object(prefix="git", key="pull_request_description.md", content=...)`

## Usage
```python
from naas_abi_marketplace.applications.git.agents.PullRequestDescriptionAgent import (
    PullRequestDescriptionAgent,
)

agent = PullRequestDescriptionAgent.New()

# Running the agent depends on the base Agent runtime.
# The configured system prompt instructs it to:
# 1) call git_diff
# 2) write a markdown PR description that starts with:
#    "This pull request resolves #<branch_name_number>"
# 3) call store_pull_request_description(description=<full markdown>)
```

## Caveats
- Requires a git repository with `origin/main` available locally; diff is computed against `origin/main...HEAD`.
- `store_pull_request_description` returns a string error (not an exception) when `description` is missing/empty; the system prompt instructs retries with full markdown.
- If `object_storage` is unavailable (module not initialized), storage returns: `"Object storage is not available (module not initialized)."`
- The system prompt mandates the final PR description begins with `This pull request resolves #<branch_name_number>` where the number is taken from the beginning of the branch name.
