from __future__ import annotations

from langchain_core.tools import tool
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
- run the project quality gate (`make_check`) and auto-fix lint (`make_fix`)
- stage files for commit (`git_add`) — ONLY when the user explicitly asks to stage/add files, or when `make_fix` produced files that are required for `make check` to pass before a PR
- commit already-staged changes (always pulls first when the branch exists on origin)
- restore accidental working-tree changes
- push the branch (ONLY when explicitly requested, or after committing `make_fix` files on the PR path) — always pulls first when the branch exists on origin
- find/create/update/view a GitHub pull request via `gh`

Decision rules (STRICT):
- NEVER call `git_add` unless the user explicitly asks to stage/add files, OR you are on the PR path and `make_fix` modified files that `make_check` needs in order to pass. A request to "commit" alone is NOT permission to stage.
- If the user asks to **commit** but does NOT explicitly ask to open/update a PR: you MUST stop after a successful commit (no PR actions).
- If the user asks to **open/update a PR** (with or without a prior commit in this turn):
  - FIRST call `make_check`. Do not create or update a PR until it reports MAKE CHECK PASSED.
  - If `make_check` fails: call `make_fix`, then `make_check` again.
  - If the second `make_check` still fails: STOP. Do not open/update the PR. Paste the failing output and tell the user to fix remaining errors.
  - If `make_fix` changed files and `make_check` then passes: `git_status`, `git_add` only those modified paths (not untracked scratch files), `git_commit` (e.g. chore: apply make check auto-fixes), `git_push`.
  - Then continue with the PR steps below. Commits already on the branch are enough; `pull_request_description` compares the branch to the base (e.g. `origin/main...HEAD`) and does not need a staged diff.
  - First check if a PR already exists for the current branch using `gh_pr_find_for_branch`.
  - If it exists: call `pull_request_description`, then update with `gh_pr_edit`, then show the PR via `gh_pr_view`.
  - If it does not exist: call `git_remote_branch_exists`. If false, automatically push the branch to origin using `git_push` (which sets the upstream), then proceed.
  - Once the branch is on origin: call `pull_request_description`, then create with `gh_pr_create`, then `gh_pr_view`.
- If the user asks to **open/update a PR** after or alongside committing: follow the commit workflow when they asked to commit; then apply the PR rules above (including `make_check` before any `gh_pr_*` call).
- Whenever a PR needs to be created/updated and the branch is not yet on origin, always push it automatically using `git_push` before attempting to create the PR.

Standard workflow — pick the path that matches the user request:

**Path PR-only** (user asked to open/update a PR and did NOT ask to commit new changes):
1) Call `make_check`. If it fails: `make_fix` → `make_check` again. If still failing, STOP and report the errors (no PR). If `make_fix` changed files and check now passes: stage those paths, commit, push.
2) Optionally call `git_status` or `git_log` for context.
3) Call `pull_request_description` and use its output as the PR body (it reflects all commits on the branch vs base).
4) If the branch name starts with digits (e.g. "123-fix-..."), ensure the PR body starts with: "This pull request resolves #123"
5) `gh_pr_find_for_branch` → if a PR exists: `gh_pr_edit` with a sensible title/body; if not: check `git_remote_branch_exists` — if false, call `git_push` to push the branch to origin first — then `gh_pr_create` → `gh_pr_view`.

**Path commit** (user asked to commit):
1) Call `git_status` and `git_diff_staged`. Treat files as staged when `git_diff_staged` lists them or when porcelain shows a non-space/`?` in the first column (`M `, `A `, `MM`, …). If the staged diff is empty, stop and tell the user to stage the files they want committed (do NOT call `git_add`).
2) Draft a Conventional Commit message (type/scope/subject) based on the staged diff only.
3) Call `git_commit` with that message — this commits only what is already staged.
4) Call `git_status` again. If lockfiles or other files were modified by hooks/tooling and remain unstaged, report them to the user; do NOT stage or commit them unless the user explicitly asks.
5) If the user explicitly asked to push, call `git_push`.
6) If the user also asked to open/update a PR, continue with **Path PR-only** from step 1 (`make_check` first).

**Path stage** (user explicitly asked to stage/add files):
1) Call `git_add` with the explicit paths the user named (or the files clearly implied by their request).
2) Never use `git add .` or `git add -A`. Pass explicit paths only.
3) If they also asked to commit, continue with **Path commit**.

Constraints:
- On commit: never stage. Commit only files already in the index. Do not invent staging for lockfiles, hooks, or "related" changes.
- When staging (only if explicitly requested): NEVER stage untracked or unrelated files (e.g. scratch notes, generated markdown like `_KICKSTART.md`). Pass explicit paths to `git_add`, which skips untracked/unchanged paths automatically.
- Do NOT use destructive git operations (no force push, no hard reset).
- Keep PR body concise: include Summary + Test plan.
- Before any push, the branch must be up to date with origin. `git_push` enforces this by running `git pull` first when the branch exists on origin; never bypass it.
"""
    model = "gpt-5.2"

    @classmethod
    def New(
        cls,
        agent_shared_state: AgentSharedState | None = None,
        agent_configuration: AgentConfiguration | None = None,
    ) -> GitAgent:

        from naas_abi_marketplace.applications.git import ABIModule


        abi_module = ABIModule.get_instance()

        registry = abi_module.engine.services.model_registry
        assert registry is not None, "ModelRegistryService not initialized"
        model = registry.get_default_chat_model()

        def _run(cmd: list[str]) -> str:
            import subprocess

            out = subprocess.check_output(cmd, stderr=subprocess.STDOUT).decode("utf-8")
            return out.strip()

        def _run_allow_fail(cmd: list[str]) -> tuple[int, str]:
            import subprocess

            proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
            output = (proc.stdout or "") + (proc.stderr or "")
            return proc.returncode, output.strip()

        def _cmd_output_text(value: str | bytes | None) -> str:
            if value is None:
                return ""
            if isinstance(value, bytes):
                return value.decode("utf-8", errors="replace")
            return value

        def _truncate_cmd_output(output: str, limit: int = 20000) -> str:
            text = output.strip()
            if len(text) <= limit:
                return text
            return text[-limit:]

        @tool(
            description=(
                "Run `make check` (lint, typecheck, security). "
                "Call this before opening or updating a pull request. "
                "Returns MAKE CHECK PASSED or MAKE CHECK FAILED plus the command output."
            )
        )
        def make_check() -> str:
            import subprocess

            try:
                proc = subprocess.run(
                    ["make", "check"],
                    capture_output=True,
                    text=True,
                    check=False,
                    timeout=600,
                )
            except FileNotFoundError:
                return "MAKE CHECK FAILED (make is not installed)"
            except subprocess.TimeoutExpired as exc:
                # TimeoutExpired.stdout/stderr are str | bytes | None in typeshed,
                # even when subprocess.run(..., text=True) was used.
                partial = (
                    _cmd_output_text(exc.stdout) + _cmd_output_text(exc.stderr)
                ).strip()
                return (
                    "MAKE CHECK FAILED (timed out after 600s)\n"
                    + _truncate_cmd_output(partial)
                )
            output = _truncate_cmd_output((proc.stdout or "") + (proc.stderr or ""))
            if proc.returncode == 0:
                return f"MAKE CHECK PASSED\n{output}"
            return f"MAKE CHECK FAILED (exit {proc.returncode})\n{output}"

        @tool(
            description=(
                "Auto-fix lint where possible. Prefers `make fix`; if that target "
                "is missing, runs `uvx ruff check --fix` on src/ (or .). "
                "After this, re-run `make_check`. Do not invent unrelated edits."
            )
        )
        def make_fix() -> str:
            import os
            import subprocess

            code, output = _run_allow_fail(["make", "fix"])
            if code == 0:
                return f"MAKE FIX PASSED\n{_truncate_cmd_output(output)}"
            no_rule = "No rule to make target" in output
            if not no_rule and code != 2:
                return f"MAKE FIX FAILED (exit {code})\n{_truncate_cmd_output(output)}"
            target = "src" if os.path.isdir("src") else "."
            proc = subprocess.run(
                ["uvx", "ruff", "check", target, "--fix"],
                capture_output=True,
                text=True,
                check=False,
                timeout=300,
            )
            fallback = _truncate_cmd_output(
                (proc.stdout or "") + (proc.stderr or "")
            )
            prefix = (
                "make fix unavailable; ran uvx ruff check --fix "
                f"{target} instead.\n"
            )
            if proc.returncode == 0:
                return f"MAKE FIX PASSED\n{prefix}{fallback}"
            return (
                f"MAKE FIX FAILED (ruff exit {proc.returncode})\n{prefix}{fallback}"
            )

        def _staged_paths_from_porcelain(status: str) -> list[str]:
            paths: list[str] = []
            for line in status.splitlines():
                if len(line) < 4 or line.startswith("##"):
                    continue
                # Porcelain v1: XY<space>PATH — X is the index (staged) column.
                if line[0] in " ?":
                    continue
                path = line[3:]
                if " -> " in path:
                    path = path.split(" -> ", 1)[1]
                paths.append(path)
            return paths

        @tool(description="Get current branch and porcelain git status")
        def git_status() -> str:
            branch = _run(["git", "branch", "--show-current"])
            status = _run(["git", "status", "--porcelain=v1", "-b"])
            staged = _staged_paths_from_porcelain(status)
            staged_summary = f"staged_count={len(staged)}"
            if staged:
                staged_summary += f"\nstaged_files={', '.join(staged)}"
            return f"{status}\n\nbranch={branch}\n{staged_summary}"

        @tool(description="Get staged git diff (what will be committed)")
        def git_diff_staged() -> str:
            _code, names = _run_allow_fail(
                ["git", "--no-pager", "diff", "--staged", "--name-only"]
            )
            staged_files = [n for n in names.splitlines() if n.strip()]
            if not staged_files:
                return (
                    "STAGED DIFF: empty. Nothing is staged. "
                    "Do not commit. Tell the user to stage files first."
                )
            _code, stat = _run_allow_fail(
                ["git", "--no-pager", "diff", "--staged", "--stat"]
            )
            _code, diff = _run_allow_fail(["git", "--no-pager", "diff", "--staged"])
            listed = "\n".join(f"- {path}" for path in staged_files)
            return (
                f"STAGED DIFF: {len(staged_files)} file(s) ARE staged "
                f"and will be committed:\n{listed}\n\n{stat}\n\n{diff}"
            )

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

        @tool(
            description=(
                "Stage files for the next commit (git add). ONLY call this when "
                "the user explicitly asks to stage/add files — never as part of "
                "a plain commit request. Provide the list of paths to stage. "
                "Only paths that are actual changes to tracked files are staged; "
                "untracked and unchanged paths are skipped so that unrelated "
                "files are never committed."
            )
        )
        def git_add(paths: list[str]) -> str:
            if not paths:
                return "No paths provided to stage."

            to_stage: list[str] = []
            skipped: list[str] = []
            for path in paths:
                # Porcelain status for this path: empty => no change;
                # every line starting with "??" => untracked (a new file, not a
                # change to a tracked file).
                status = _run(["git", "status", "--porcelain", "--", path])
                lines = [line for line in status.splitlines() if line]
                if not lines:
                    skipped.append(f"{path} (no changes)")
                elif all(line.startswith("??") for line in lines):
                    skipped.append(f"{path} (untracked)")
                else:
                    to_stage.append(path)

            if to_stage:
                code, output = _run_allow_fail(["git", "add", "--", *to_stage])
                if code != 0:
                    raise RuntimeError(f"git add failed:\n{output}")

            parts = []
            if to_stage:
                parts.append(f"Staged: {', '.join(to_stage)}")
            if skipped:
                parts.append(f"Skipped (not a tracked change): {', '.join(skipped)}")
            return " | ".join(parts) if parts else "Nothing to stage."

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
                "Provide the full commit message including body. "
                "Always runs `git pull` first when the branch exists on origin."
            )
        )
        def git_commit(message: str) -> str:
            import subprocess

            if not message or not message.strip():
                raise ValueError("Commit message is required.")

            # `git diff --cached --quiet` exits 0 when nothing is staged.
            staged_code, _ = _run_allow_fail(["git", "diff", "--cached", "--quiet"])
            if staged_code == 0:
                return (
                    "Nothing is staged to commit. Ask the user to stage the "
                    "files they want included (or call `git_add` only if they "
                    "explicitly asked to stage). Do not stage files on your own "
                    "and do not retry `git_commit` until something is staged."
                )

            branch = _run(["git", "branch", "--show-current"])
            remote_code, _ = _run_allow_fail(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", branch]
            )
            pull_output = ""
            if remote_code == 0:
                pull_code, pull_output = _run_allow_fail(
                    ["git", "pull", "origin", branch]
                )
                if pull_code != 0:
                    raise RuntimeError(
                        f"git pull failed before commit (resolve conflicts and retry):\n{pull_output}"
                    )

            proc = subprocess.run(
                ["git", "commit", "-m", message, "-n"],
                capture_output=True,
                text=True,
                check=False,
            )
            output = (proc.stdout or "") + (proc.stderr or "")
            if proc.returncode != 0:
                raise RuntimeError(f"git commit failed:\n{output.strip()}")
            return f"{pull_output}\n{output}".strip()

        @tool(
            description=(
                "Push current branch to origin (sets upstream if needed). "
                "Always runs `git pull` first when the branch already exists on origin."
            )
        )
        def git_push() -> str:
            branch = _run(["git", "branch", "--show-current"])
            remote_code, _ = _run_allow_fail(
                ["git", "ls-remote", "--exit-code", "--heads", "origin", branch]
            )
            pull_output = ""
            if remote_code == 0:
                pull_code, pull_output = _run_allow_fail(
                    ["git", "pull", "origin", branch]
                )
                if pull_code != 0:
                    raise RuntimeError(
                        f"git pull failed before push (resolve conflicts and retry):\n{pull_output}"
                    )
            code, output = _run_allow_fail(["git", "push", "-u", "origin", branch])
            if code != 0:
                # Try non-upstream push if already set
                code2, output2 = _run_allow_fail(["git", "push"])
                if code2 != 0:
                    raise RuntimeError(f"git push failed:\n{output}\n{output2}")
                return f"{pull_output}\n{output2}".strip()
            return f"{pull_output}\n{output}".strip()

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
                git_add,
                git_restore,
                git_commit,
                git_push,
                git_remote_branch_exists,
                make_check,
                make_fix,
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
