"""Abi tools for Nexus Slides projects (Forgejo-backed decks).

Read/write/list/history against ``slides/<slug>/deck.html`` on branch
``slides/<slug>``. Does not surface Coder workspaces.
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi_core.services.agent.context import agent_user_id
from naas_abi_core.services.source_control.SourceControlPorts import SourceControlError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BRANCH_PREFIX = "slides/"


def _get_source_control():
    from naas_abi import ABIModule

    return ABIModule.get_instance().engine.services.source_control


def _repo_id() -> str:
    try:
        from naas_abi.apps.nexus.apps.api.app.core.config import settings

        return settings.coding_repo_id or "abi/monorepo"
    except Exception:
        return "abi/monorepo"


def _branch(slug: str) -> str:
    return f"{_BRANCH_PREFIX}{slug}"


def _deck_path(slug: str) -> str:
    return f"slides/{slug}/deck.html"


def _project_path(slug: str) -> str:
    return f"slides/{slug}/project.json"


def slides_tools() -> list[BaseTool]:
    @tool
    def list_slides_projects() -> dict[str, Any]:
        """List Slides projects in the workspace monorepo (branches slides/<slug>)."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        try:
            sc = _get_source_control()
            repo_id = _repo_id()
            projects = []
            for branch in sc.list_branches(repo_id=repo_id):
                if not branch.name.startswith(_BRANCH_PREFIX):
                    continue
                slug = branch.name[len(_BRANCH_PREFIX) :]
                if not _SLUG_RE.match(slug):
                    continue
                title = slug.replace("-", " ").title()
                try:
                    meta = sc.get_file(
                        repo_id=repo_id, path=_project_path(slug), ref=branch.name
                    )
                    if meta.text:
                        data = json.loads(meta.text)
                        title = str(data.get("title") or title)
                except (SourceControlError, json.JSONDecodeError):
                    pass
                projects.append(
                    {
                        "slug": slug,
                        "title": title,
                        "branch": branch.name,
                        "deck_path": _deck_path(slug),
                    }
                )
            return {"projects": projects}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def read_slides_deck(slug: str) -> dict[str, Any]:
        """Read the HTML deck for a Slides project slug."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        try:
            sc = _get_source_control()
            file = sc.get_file(
                repo_id=_repo_id(), path=_deck_path(slug), ref=_branch(slug)
            )
            if file.is_binary or file.text is None:
                return {"error": "Deck is not UTF-8 text"}
            return {"slug": slug, "path": _deck_path(slug), "html": file.text}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def write_slides_deck(
        slug: str, html: str, message: str = "Update slides deck via Abi"
    ) -> dict[str, Any]:
        """Write and commit the HTML deck for a Slides project slug.

        Prefer editing the existing deck structure. Keep buildPptx() in sync
        with visible slides when you change content. PPTX export is best-effort
        vs the HTML preview.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        if not html or not html.strip():
            return {"error": "html must be a non-empty string"}
        try:
            sc = _get_source_control()
            commit = sc.upsert_file(
                repo_id=_repo_id(),
                path=_deck_path(slug),
                content=html,
                message=message or "Update slides deck via Abi",
                branch=_branch(slug),
            )
            return {
                "slug": slug,
                "path": _deck_path(slug),
                "commit_sha": commit.sha,
                "message": commit.message,
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def slides_history(slug: str, limit: int = 10) -> dict[str, Any]:
        """List recent commits on a Slides project branch."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        try:
            sc = _get_source_control()
            commits = sc.list_commits(
                repo_id=_repo_id(),
                ref=_branch(slug),
                limit=max(1, min(int(limit or 10), 50)),
            )
            return {
                "slug": slug,
                "commits": [
                    {
                        "sha": c.sha,
                        "message": c.message,
                        "author": c.author,
                        "date": c.date,
                    }
                    for c in commits
                ],
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    return [
        list_slides_projects,
        read_slides_deck,
        write_slides_deck,
        slides_history,
    ]
