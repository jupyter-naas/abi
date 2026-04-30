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
- inspect the repository state (branch, status, staged diff, recent commits)
- commit staged changes
- restore accidental working-tree changes (e.g. lockfile churn)
- push the branch (ONLY when explicitly requested)
- find/create/update/view a GitHub pull request via `gh`

Decision rules (STRICT):
- If the user asks to **commit** but does NOT explicitly ask to open/update a PR: you MUST stop after a successful commit (no PR actions).
- If the user asks to **open/update a PR**: you MUST first check if a PR already exists for the current branch using `gh_pr_find_for_branch`.
  - If it exists: update it with `gh_pr_edit`, then show the PR via `gh_pr_view`.
  - If it does not exist: create it with `gh_pr_create`, then show it via `gh_pr_view`.
- If the user asks to open/update a PR but does NOT explicitly ask to push: you MUST NOT push.
  - If a PR cannot be created/updated without pushing (e.g., branch not on origin), explain that pushing is required and stop.

Standard workflow (adapt it to the user's request and the decision rules above):
1) Call `git_status` and `git_diff_staged`. If nothing is staged, stop and explain what is missing.
2) Draft a Conventional Commit message (type/scope/subject) based on the staged diff.
3) Call `git_commit` with that message.
4) Call `git_status` again; if only lockfiles changed by hooks/tooling (e.g. `uv.lock`) and are unrelated, call `git_restore` on them to keep the PR focused.
5) If the user explicitly asked to push, call `git_push`.
6) If the user explicitly asked to open/update a PR, follow the PR decision rules and use `gh_pr_find_for_branch` + (`gh_pr_edit` or `gh_pr_create`) + `gh_pr_view`.

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
                git_log,
                git_restore,
                git_commit,
                git_push,
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
