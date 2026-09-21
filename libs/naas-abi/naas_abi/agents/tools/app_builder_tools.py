"""AppsAgent builder tools: create and edit static apps in the Apps editor.

An app project is ``manifest.json`` plus HTML/CSS/JS (no build). Tools write
the project's draft, the same working copy the editor shows on the left and
the preview renders in the middle, so every write shows up live. Save makes
a git commit; submit sends the app to its source repository for review.

The tools call ``AppProjectsService`` in-process (no coding sandbox), after
the same workspace membership check as ``/api/app-projects``. When the user
has a project open, the pane sends it as the open feature resource
(``app_project``) and tools default to it.
"""

from __future__ import annotations

import re
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.feature.context import (
    active_feature_errors,
    active_feature_resource_id,
)
from naas_abi.agents.tools.nexus_admin_tools import (
    _require_user_id,
    _run_async,
    _with_db,
    _workspace_service,
)
from naas_abi_core.services.agent.context import agent_workspace_id

APP_PROJECT_RESOURCE_KIND = "app_project"
# Tools that change a project. The web mirrors this list
# (isAppProjectWriteTool) to refresh the editor and the preview.
APP_PROJECT_WRITE_TOOLS = (
    "create_app_project",
    "edit_module_app",
    "write_app_file",
    "replace_in_app_file",
    "delete_app_file",
    "save_app_project",
    "submit_app_project",
)
_MAX_READ_CHARS = 60_000
_DATA_URL_RE = re.compile(r"data:[a-zA-Z0-9.+/-]+;base64,[A-Za-z0-9+/=\s]{200,}")


def _tool_error(exc: BaseException) -> dict[str, str]:
    from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
        AppProjectError,
    )

    if isinstance(exc, AppProjectError):
        return {"error": str(exc)}
    logger = __import__("logging").getLogger(__name__)
    logger.exception("app builder tool failed: %s", type(exc).__name__)
    return {"error": "App project operation failed. Check server logs for details."}


def _caller() -> tuple[str, str, Any] | dict[str, str]:
    """``(workspace_id, user_id, author)`` after the membership check."""
    user_id = _require_user_id()
    if isinstance(user_id, dict):
        return user_id
    workspace_id = (agent_workspace_id.get() or "").strip()
    if not workspace_id:
        return {
            "error": "No workspace on this session. Open the chat pane from a workspace."
        }

    async def _check(db: Any) -> Any:
        from naas_abi.apps.nexus.apps.api.app.models import UserModel
        from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
            AppAuthor,
        )
        from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import (
            WorkspacePermissionError,
        )
        from sqlalchemy import select

        try:
            await _workspace_service(db).require_workspace_access(
                user_id=user_id, workspace_id=workspace_id
            )
        except WorkspacePermissionError:
            return {"error": "You do not have access to this workspace."}
        row = (
            (await db.execute(select(UserModel).where(UserModel.id == user_id)))
            .scalars()
            .first()
        )
        email = str(getattr(row, "email", "") or "")
        name = (
            str(getattr(row, "name", "") or "") or email.split("@")[0] or "Nexus user"
        )
        return AppAuthor(user_id=user_id, name=name, email=email)

    author = _run_async(_with_db(_check))
    if isinstance(author, dict):
        return author
    return workspace_id, user_id, author


def _service() -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.apps.projects.factory import (
        build_app_projects_service,
    )

    return build_app_projects_service()


def _key(workspace_id: str, slug: str) -> Any:
    from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
        AppProjectKey,
    )

    return AppProjectKey(workspace_id, slug)


def _resolve_slug(slug: str) -> str | dict[str, str]:
    explicit = (slug or "").strip()
    if explicit:
        return explicit
    open_slug = active_feature_resource_id(APP_PROJECT_RESOURCE_KIND)
    if open_slug:
        return open_slug
    return {
        "error": "No app project is open. Pass slug (see list_app_projects), or "
        "create one with create_app_project."
    }


def _editor_link(workspace_id: str, slug: str) -> str:
    return f"/workspace/{workspace_id}/apps/p/{slug}"


def _summary(info: Any, workspace_id: str) -> dict[str, Any]:
    meta = info.meta
    out: dict[str, Any] = {
        "slug": meta.slug,
        "title": meta.title,
        "unsaved_changes": info.dirty,
        "entry": info.entry,
        "editor": _editor_link(workspace_id, meta.slug),
    }
    if meta.origin is not None:
        out["copied_from"] = meta.origin.app_id
    if meta.submission is not None:
        out["submitted_branch"] = meta.submission.branch
    if info.files:
        out["files"] = [f.path for f in info.files]
    return out


def _with_project(slug: str, fn: Any) -> Any:
    caller = _caller()
    if isinstance(caller, dict):
        return caller
    workspace_id, _user_id, author = caller
    resolved = _resolve_slug(slug)
    if isinstance(resolved, dict):
        return resolved
    try:
        return fn(_service(), _key(workspace_id, resolved), author, workspace_id)
    except Exception as exc:  # noqa: BLE001
        return _tool_error(exc)


def app_builder_tools() -> list[BaseTool]:
    @tool
    def list_app_projects() -> Any:
        """List this workspace's app projects (apps built or copied in Nexus).

        Each row: slug, title, unsaved_changes, copied_from (module app it was
        duplicated from), submitted_branch, editor (link to open it).
        """
        caller = _caller()
        if isinstance(caller, dict):
            return caller
        workspace_id, _user_id, _author = caller
        try:
            return [
                _summary(p, workspace_id)
                for p in _service().list_projects(workspace_id)
            ]
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def create_app_project(
        title: str, description: str = "", icon_emoji: str = ""
    ) -> Any:
        """Create a new app project from the static starter (manifest.json,
        index.html, styles.css, app.js) and return its slug and editor link.

        Then build the app with write_app_file. Only when the user asks for a
        new app; to change an existing module app, use edit_module_app.
        """
        caller = _caller()
        if isinstance(caller, dict):
            return caller
        workspace_id, _user_id, author = caller
        try:
            info = _service().create_project(
                workspace_id,
                title=title,
                author=author,
                description=description,
                icon_emoji=icon_emoji or "✨",
            )
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)
        return {"created": True, **_summary(info, workspace_id)}

    @tool
    def edit_module_app(app_id: str) -> Any:
        """Duplicate a module app (app_id like "bob:budget", see
        list_workspace_apps) into a new app project to edit it.

        The original stays unchanged and keeps serving; the copy is edited in
        Nexus and later submitted to the source repository for review.
        """
        caller = _caller()
        if isinstance(caller, dict):
            return caller
        workspace_id, _user_id, author = caller
        chosen = (app_id or "").strip() or (active_feature_resource_id("app") or "")
        if not chosen:
            return {
                "error": "Pass the module app_id to copy (see list_workspace_apps)."
            }
        try:
            info = _service().import_module_app(
                workspace_id, app_id=chosen, author=author
            )
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)
        return {"created": True, **_summary(info, workspace_id)}

    @tool
    def list_app_files(slug: str = "") -> Any:
        """List the files of the open app project (or ``slug``) with sizes,
        the HTML entry page, and whether there are unsaved changes."""

        def _run(service: Any, key: Any, _author: Any, workspace_id: str) -> Any:
            info = service.get_project(key)
            out = _summary(info, workspace_id)
            out["files"] = [{"path": f.path, "size": f.size} for f in info.files]
            return out

        return _with_project(slug, _run)

    @tool
    def read_app_file(path: str, slug: str = "") -> Any:
        """Read a text file of the open app project (live draft)."""

        def _run(service: Any, key: Any, _author: Any, _ws: str) -> Any:
            data = service.read_file(key, path)
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                return {"path": path, "binary": True, "size": len(data)}
            text, redacted = _DATA_URL_RE.subn("[DATA_URL]", text)
            out: dict[str, Any] = {"path": path, "size": len(data), "content": text}
            if len(text) > _MAX_READ_CHARS:
                out["content"] = text[:_MAX_READ_CHARS] + "\n...[truncated]..."
                out["warning"] = (
                    "Truncated. Edit with replace_in_app_file instead of rewriting the file."
                )
            if redacted:
                out["note"] = f"{redacted} embedded data URLs shown as [DATA_URL]."
            return out

        return _with_project(slug, _run)

    @tool
    def write_app_file(path: str, content: str, slug: str = "") -> Any:
        """Create or overwrite a text file in the open app project.

        Paths are relative to the app root (index.html, css/app.css). Use
        relative links between files. The preview reloads right after. Write
        whole files; for a small change to a large file use replace_in_app_file.
        """

        def _run(service: Any, key: Any, _author: Any, _ws: str) -> Any:
            written = service.write_file(key, path, content)
            return {"written": written.path, "size": written.size, "saved": False}

        return _with_project(slug, _run)

    @tool
    def replace_in_app_file(path: str, old: str, new: str, slug: str = "") -> Any:
        """Replace one exact occurrence of ``old`` with ``new`` in a file of
        the open app project. ``old`` must appear exactly once: include enough
        surrounding text to make it unique."""

        def _run(service: Any, key: Any, _author: Any, _ws: str) -> Any:
            text = service.read_file(key, path).decode("utf-8")
            count = text.count(old) if old else 0
            if count != 1:
                return {
                    "error": f"old text found {count} times in {path}; it must be exactly once.",
                    "hint": "Call read_app_file and copy a longer, unique snippet.",
                }
            written = service.write_file(key, path, text.replace(old, new, 1))
            return {"written": written.path, "size": written.size, "saved": False}

        return _with_project(slug, _run)

    @tool
    def delete_app_file(path: str, slug: str = "") -> Any:
        """Delete a file from the open app project."""

        def _run(service: Any, key: Any, _author: Any, _ws: str) -> Any:
            service.delete_file(key, path)
            return {"deleted": path, "saved": False}

        return _with_project(slug, _run)

    @tool
    def check_app(slug: str = "") -> Any:
        """Check the open app project: manifest.json, the entry page, broken
        relative links, and the runtime errors the live preview reported.
        Call it after edits and before saving."""

        def _run(service: Any, key: Any, _author: Any, _ws: str) -> Any:
            issues = [
                {"level": i.level, "message": i.message, "path": i.path}
                for i in service.check(key)
            ]
            errors = active_feature_errors()
            return {
                "issues": issues,
                "preview_errors": errors,
                "ok": not errors and not any(i["level"] == "error" for i in issues),
            }

        return _with_project(slug, _run)

    @tool
    def save_app_project(message: str = "", slug: str = "") -> Any:
        """Save the open app project: one git commit with every change since
        the last save. ``message`` is the commit message (conventional,
        e.g. "feat(apps): add a chart")."""

        def _run(service: Any, key: Any, author: Any, _ws: str) -> Any:
            commit = service.save(key, author=author, message=message or None)
            if commit is None:
                return {"saved": False, "note": "Nothing changed since the last save."}
            return {"saved": True, "commit": commit.sha[:12], "message": commit.message}

        return _with_project(slug, _run)

    @tool
    def submit_app_project(module: str = "", slug: str = "") -> Any:
        """Submit the open app project to its source repository as a new
        branch for the tech team to review. Only when the user asks.

        A copied module app goes back to its own folder; a new app goes under
        ``module`` (default bob). Saves first. Fails clearly when submitting
        is not configured on this platform.
        """

        def _run(service: Any, key: Any, author: Any, _ws: str) -> Any:
            submission = service.submit(key, author=author, module=module or None)
            return {
                "submitted": True,
                "branch": submission.branch,
                "url": submission.url,
                "pull_request": submission.pull_request_url,
                "target_path": submission.target_path,
            }

        return _with_project(slug, _run)

    return [
        list_app_projects,
        create_app_project,
        edit_module_app,
        list_app_files,
        read_app_file,
        write_app_file,
        replace_in_app_file,
        delete_app_file,
        check_app,
        save_app_project,
        submit_app_project,
    ]
