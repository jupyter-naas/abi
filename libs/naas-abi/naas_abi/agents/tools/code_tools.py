"""CodeAgent tools for Nexus Code (repos, branches, pull requests).

Read side of ``/api/coding-environments`` (``/repos``, ``/branches``) and the
code review surface, through the engine ``source_control`` service (Forgejo in
production, ``local_git`` in dev), with the same workspace membership check.
Editing the open repo's sandbox checkout stays in ``coding_tools``
(``read_coding_file``, ``write_coding_file``, ``run_in_coding_sandbox``, ...),
which act on the repo/branch bound by ``context.coding``.
"""

from __future__ import annotations

from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import active_feature_resource_id
from naas_abi.agents.feature.runtime import check_member, clip, guarded, tool_context
from naas_abi_core.services.agent.context import (
    coding_active_branch,
    coding_active_repo,
)

REPO_RESOURCE_KIND = "repo"
_FEATURE = "Code"


def _source_control() -> Any | None:
    from naas_abi import ABIModule

    try:
        return ABIModule.get_instance().engine.services.source_control
    except AssertionError:  # engine asserts when no git backend is configured
        return None


def _default_repo() -> str:
    try:
        from naas_abi.apps.nexus.apps.api.app.core.config import settings

        return settings.coding_repo_id or ""
    except Exception:  # noqa: BLE001
        return ""


def _repo_id(repo_id: str) -> str:
    return (
        (repo_id or "").strip()
        or (coding_active_repo.get() or "").strip()
        or (active_feature_resource_id(REPO_RESOURCE_KIND) or "")
        or _default_repo()
    )


def _call(fn: Any) -> Any:
    ctx = tool_context()
    if isinstance(ctx, dict):
        return ctx
    user_id, workspace_id = ctx

    def _run() -> Any:
        role = check_member(user_id, workspace_id)
        if isinstance(role, dict):
            return role
        source_control = _source_control()
        if source_control is None:
            return {
                "error": "No git backend (source_control) is configured on this deployment."
            }
        return fn(source_control)

    return guarded(_FEATURE, _run)


def code_tools() -> list[BaseTool]:
    @tool
    def list_code_repositories() -> Any:
        """Repositories available in Nexus Code (the configured default first),
        plus the repo and branch open in the Code view, if any."""
        open_repo = (coding_active_repo.get() or "").strip() or None
        open_branch = (coding_active_branch.get() or "").strip() or None
        default = _default_repo()

        def _list(source_control: Any) -> Any:
            repos = source_control.list_repos()
            rows = [
                {
                    "repo_id": f"{r.owner}/{r.name}",
                    "description": clip(r.description, 160),
                    "default_branch": r.default_branch,
                    "empty": r.empty,
                }
                for r in repos
            ]
            rows.sort(
                key=lambda r: (r["repo_id"] != default, str(r["repo_id"]).lower())
            )
            return {
                "default_repo": default or None,
                "open_repo": open_repo,
                "open_branch": open_branch,
                "repos": rows[:100],
            }

        return _call(_list)

    @tool
    def list_code_branches(repo_id: str = "") -> Any:
        """Branches of a repo (owner/name). Omit repo_id to use the open repo,
        else the configured default."""
        repo = _repo_id(repo_id)
        if not repo:
            return {
                "error": "No repo is open and no default is configured. Pass repo_id."
            }

        def _list(source_control: Any) -> Any:
            branches = source_control.list_branches(repo_id=repo)
            return {
                "repo_id": repo,
                "branches": [
                    {"name": b.name, "protected": getattr(b, "protected", False)}
                    for b in branches[:200]
                ],
            }

        return _call(_list)

    @tool
    def list_pull_requests(repo_id: str = "", state: str = "open") -> Any:
        """Pull requests (proposals) of a repo: number, title, state, source and
        target branches, author. state is open, closed, or all. Omit repo_id to
        use the open repo."""
        repo = _repo_id(repo_id)
        if not repo:
            return {
                "error": "No repo is open and no default is configured. Pass repo_id."
            }
        wanted = state if state in {"open", "closed", "all"} else "open"

        def _list(source_control: Any) -> Any:
            proposals = source_control.list_proposals(repo_id=repo, state=wanted)
            return {
                "repo_id": repo,
                "state": wanted,
                "pull_requests": [
                    {
                        "number": p.number,
                        "title": clip(p.title, 160),
                        "state": p.state,
                        "source_branch": p.source_branch,
                        "target_branch": p.target_branch,
                        "author": p.author,
                    }
                    for p in proposals[:60]
                ],
            }

        return _call(_list)

    return [list_code_repositories, list_code_branches, list_pull_requests]
