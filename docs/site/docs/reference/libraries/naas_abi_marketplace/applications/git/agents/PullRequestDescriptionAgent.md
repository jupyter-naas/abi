# PullRequestDescriptionAgent

## What it is
- An `Agent` factory and minimal agent class used to generate and persist a GitHub pull request description based on the current branch name and the diff against `origin/main`.
- Provides two LangChain tools to:
  - fetch the branch name + git diff
  - store a generated PR description to `storage/datastore/git/pull_request_description.md` (and a timestamped copy)

## Public API
- `create_agent(agent_shared_state: Optional[AgentSharedState] = None, agent_configuration: Optional[AgentConfiguration] = None) -> Optional[Agent]`
  - Creates and returns a configured `PullRequestDescriptionAgent` instance.
  - Sets a default `system_prompt` (instructions for tool usage and output formatting).
  - Registers two tools: `git_diff` and `store_pull_request_description`.
- `class PullRequestDescriptionAgent(Agent)`
  - Concrete agent type; no additional behavior beyond the base `Agent`.

## Configuration/Dependencies
- Depends on:
  - `naas_abi_core.services.agent.Agent`: `Agent`, `AgentConfiguration`, `AgentSharedState`
  - Chat model: `naas_abi_marketplace.ai.chatgpt.models.gpt_4_1_mini.model`
  - LangChain: `langchain_core.tools.StructuredTool`
  - Pydantic: `BaseModel`, `Field`
  - System tools: `git` CLI available in environment (via `subprocess`)
- Tool behavior:
  - `git_diff` runs:
    - `git branch --show-current` to obtain the current branch name
    - `git diff origin/main -- . :!uv.lock` to generate a diff (excluding `uv.lock`)
  - `store_pull_request_description` writes to:
    - `storage/datastore/git/pull_request_description.md`
    - also copies to a timestamp-prefixed file in the same directory

## Usage
```python
from naas_abi_marketplace.applications.git.agents.PullRequestDescriptionAgent import create_agent

agent = create_agent()

# Agent execution API depends on the base `Agent` implementation.
# The agent is configured with tools and a system prompt instructing it to:
# 1) call `git_diff`
# 2) call `store_pull_request_description`
# 3) output a PR description starting with:
#    "This pull request resolves #<branch_name_number>"
```

## Caveats
- Requires a git repository with an `origin/main` reference available locally.
- The diff is computed against `origin/main`, not the local `main`.
- The agent’s system prompt mandates that the final PR description starts with:
  - `This pull request resolves #<branch_name_number>` where the number is at the beginning of the branch name.
- Writes files under `storage/datastore/git/`; ensure the process has filesystem permissions.
