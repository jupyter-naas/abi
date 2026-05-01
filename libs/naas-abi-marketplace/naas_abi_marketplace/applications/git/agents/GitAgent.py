from __future__ import annotations

from typing import Optional

from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from naas_abi_core.services.agent.Agent import (
    Agent,
    AgentConfiguration,
    AgentSharedState,
)


class GitAgent(Agent):
    name: str = "Git Agent"
    description: str = "An agent to manage Git repositories"
    system_prompt: str = """
You are a Git automation agent.

You have access to tools that can:
- inspect the repository state (branch, status, staged diff, recent commits, whether the branch exists on origin)
- generate a pull request description by invoking the PullRequestDescriptionAgent
- commit staged changes
- restore accidental working-tree changes (e.g. lockfile churn)
- push the branch (ONLY when explicitly requested)
- find/create/update/view a GitHub pull request via `gh`

Decision rules (STRICT):
- If the user asks to **commit** but does NOT explicitly ask to open/update a PR: you MUST stop after a successful commit (no PR actions).
- If the user asks to **open/update a PR** only (no explicit request to commit new work):
  - Do NOT require staged or unstaged changes. Commits already on the branch are enough. `pull_request_description` compares the branch to the base (e.g. `origin/main...HEAD`) and does not need a staged diff.
  - First check if a PR already exists for the current branch using `gh_pr_find_for_branch`.
  - If it exists: call `pull_request_description`, then update with `gh_pr_edit`, then show the PR via `gh_pr_view`.
  - If it does not exist: call `git_remote_branch_exists`. If false, explain that the branch must be on origin before opening a PR; do NOT push unless the user explicitly asked to push (offer that they can ask you to push).
  - If the branch is on origin (or after a user-requested push): call `pull_request_description`, then create with `gh_pr_create`, then `gh_pr_view`.
- If the user asks to **open/update a PR** after or alongside committing: follow the commit workflow when they asked to commit; then apply the PR-only rules above for create/update/view.
- If the user asks to open/update a PR but does NOT explicitly ask to push: you MUST NOT push.
  - If a new PR cannot be created because the branch is not on origin, explain that pushing is required and stop (unless they explicitly asked to push).

Standard workflow — pick the path that matches the user request:

**Path PR-only** (user asked to open/update a PR and did NOT ask to commit new changes):
1) Optionally call `git_status` or `git_log` for context.
2) Call `pull_request_description` and use its output as the PR body (it reflects all commits on the branch vs base).
3) If the branch name starts with digits (e.g. "123-fix-..."), ensure the PR body starts with: "This pull request resolves #123"
4) `gh_pr_find_for_branch` → if a PR exists: `gh_pr_edit` with a sensible title/body; if not: ensure branch is on origin (`git_remote_branch_exists`), then `gh_pr_create` if possible → `gh_pr_view`.

**Path commit** (user asked to commit):
1) Call `git_status` and `git_diff_staged`. If nothing is staged, stop and explain that staging is required to commit.
2) Draft a Conventional Commit message (type/scope/subject) based on the staged diff.
3) Call `git_commit` with that message.
4) Call `git_status` again; if only lockfiles changed by hooks/tooling (e.g. `uv.lock`) and are unrelated, call `git_restore` on them to keep the PR focused.
5) If the user explicitly asked to push, call `git_push`.
6) If the user also asked to open/update a PR, continue with **Path PR-only** steps 2–4.

Constraints:
- Do NOT use destructive git operations (no force push, no hard reset).
- Keep PR body concise: include Summary + Test plan.
"""
    model = "gpt-4.1-mini"

    @classmethod
    def New(
        cls,
        agent_shared_state: Optional[AgentSharedState] = None,
        agent_configuration: Optional[AgentConfiguration] = None,
    ) -> "GitAgent":

        from naas_abi_marketplace.applications.git import ABIModule
        from pydantic import SecretStr

        module = ABIModule.get_instance()
        secret = module.engine.services.secret
        model = ChatOpenAI(
            model=cls.model, api_key=SecretStr(secret.get("OPENAI_API_KEY"))
        )

        def _run(cmd: list[str]) -> str:
            import subprocess

            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
            return out.strip()

        def _run_allow_fail(cmd: list[str]) -> tuple[int, str]:
            import subprocess

            proc = subprocess.run(cmd, capture_output=True, text=True)
            output = (proc.stdout or "") + (proc.stderr or "")
            return proc.returncode, output.strip()

        @tool(description="Get current branch and porcelain git status")
        def git_status() -> str:
            branch = _run(["git", "branch", "--show-current"])
            status = _run(["git", "status", "--porcelain=v1", "-b"])
            return f"{status}\n\nbranch={branch}"

        @tool(description="Get staged git diff (what will be committed)")
        def git_diff_staged() -> str:
            return _run(["git", "diff", "--staged"])

        @tool(
            description=(
                "Create a pull request description for the current branch by "
                "invoking PullRequestDescriptionAgent. Returns markdown."
            )
        )
        def pull_request_description() -> str:
            from naas_abi_marketplace.applications.git.agents.PullRequestDescriptionAgent import (
                PullRequestDescriptionAgent,
            )

            agent = PullRequestDescriptionAgent.New()
            return agent.invoke(
                "Generate the pull request description for the current branch. "
                "Return the markdown only."
            )

        @tool(description="Get recent git commits (one line each)")
        def git_log(limit: int = 10) -> str:
            return _run(["git", "log", f"-{limit}", "--oneline"])

        @tool(description="Restore files to HEAD (discard working-tree changes)")
        def git_restore(paths: list[str]) -> str:
            if not paths:
                return "No paths provided."
            code, output = _run_allow_fail(["git", "checkout", "--", *paths])
            if code != 0:
                raise RuntimeError(f"git checkout failed:\n{output}")
            return f"Restored: {', '.join(paths)}"

        @tool(
            description=(
                "Create a git commit from staged changes. "
                "Provide the full commit message including body."
            )
        )
        def git_commit(message: str) -> str:
            import subprocess

            if not message or not message.strip():
                raise ValueError("Commit message is required.")
            proc = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode != 0:
                raise RuntimeError(f"git commit failed:\n{output.strip()}")
            return output.strip()

        @tool(description="Push current branch to origin (sets upstream if needed)")
        def git_push() -> str:
            branch = _run(["git", "branch", "--show-current"])
            code, output = _run_allow_fail(["git", "push", "-u", "origin", branch])
            if code != 0:
                # Try non-upstream push if already set
                code2, output2 = _run_allow_fail(["git", "push"])
                if code2 != 0:
                    raise RuntimeError(f"git push failed:\n{output}\n{output2}")
                return output2
            return output

        @tool(
            description=(
                "Check whether the current branch exists on origin "
                "(returns 'true' or 'false')."
            )
        )
        def git_remote_branch_exists() -> str:
            branch = _run(["git", "branch", "--show-current"])
            code, _output = _run_allow_fail(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", branch]
            )
            return "true" if code == 0 else "false"

        @tool(description="Create a GitHub PR using gh (returns URL)")
        def gh_pr_create(title: str, body: str, base: str = "main") -> str:
            if not title.strip():
                raise ValueError("PR title is required.")
            if not body.strip():
                raise ValueError("PR body is required.")
            branch = _run(["git", "branch", "--show-current"])
            return _run(
                [
                    "gh",
                    "pr",
                    "create",
                    "--base",
                    base,
                    "--head",
                    branch,
                    "--title",
                    title,
                    "--body",
                    body,
                ]
            )

        @tool(
            description=(
                "Find an existing PR for the current branch. "
                "Returns JSON list (possibly empty) with url/number/title."
            )
        )
        def gh_pr_find_for_branch() -> str:
            branch = _run(["git", "branch", "--show-current"])
            return _run(
                [
                    "gh",
                    "pr",
                    "list",
                    "--head",
                    branch,
                    "--json",
                    "url,number,title,baseRefName,headRefName",
                ]
            )

        @tool(description="Edit an existing PR title/body by number")
        def gh_pr_edit(number: int, title: str, body: str) -> str:
            if number <= 0:
                raise ValueError("PR number must be positive.")
            if not title.strip():
                raise ValueError("PR title is required.")
            if not body.strip():
                raise ValueError("PR body is required.")
            return _run(
                [
                    "gh",
                    "pr",
                    "edit",
                    str(number),
                    "--title",
                    title,
                    "--body",
                    body,
                ]
            )

        @tool(description="View the current PR (URL/number/title/base/head)")
        def gh_pr_view() -> str:
            return _run(
                [
                    "gh",
                    "pr",
                    "view",
                    "--json",
                    "url,number,title,baseRefName,headRefName",
                ]
            )

        if agent_configuration is None:
            agent_configuration = AgentConfiguration(system_prompt=cls.system_prompt)
        if agent_shared_state is None:
            agent_shared_state = AgentSharedState(thread_id="0")

        return GitAgent(
            name=cls.name,
            description=cls.description,
            chat_model=model,
            tools=[
                git_status,
                git_diff_staged,
                pull_request_description,
                git_log,
                git_restore,
                git_commit,
                git_push,
                git_remote_branch_exists,
                gh_pr_create,
                gh_pr_find_for_branch,
                gh_pr_edit,
                gh_pr_view,
            ],
            agents=[],
            state=agent_shared_state,
            configuration=agent_configuration,
            memory=None,
        )
