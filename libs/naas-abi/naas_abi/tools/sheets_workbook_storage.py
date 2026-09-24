"""Forgejo + Coder sidecar persistence for Nexus Sheets workbooks.

Workbooks live at ``sheets/<workspace>/<slug>/workbook.html`` on branch
``sheets/<workspace>/<slug>`` (legacy ``sheets/<slug>`` when project.json matches).
"""

from __future__ import annotations

import json
import re
import unicodedata
from collections import OrderedDict
from typing import Any

from naas_abi_core.services.agent.context import (
    agent_chat_id,
    agent_user_email,
    agent_user_id,
    agent_user_name,
    agent_workspace_id,
    coder_workspace_base,
    sheets_active_slug,
    sheets_active_title,
    sheets_brief,
)
from naas_abi_core.services.agent.tools.workspace_tools import _call as _sidecar_call
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    SourceControlError,
)

from naas_abi.agents.sheets import (
    derive_workbook_title,
    is_placeholder_workbook_title,
)
from naas_abi.apps.nexus.sheets.html_io import (
    parse_workbook_html,
    serialize_workbook_html,
)

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BRANCH_PREFIX = "sheets/"
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_WIPED_WORKBOOK_ERROR = "API restart wiped this workbook. Click New, then retry."

_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|chore|style|refactor|docs|perf)(\([a-z0-9_.-]+\))?!?: .+"
)

_ACTIVE_SLUG_MEMO: OrderedDict[str, str] = OrderedDict()
_ACTIVE_SLUG_MEMO_MAX = 256


def require_agent_access(*, write: bool = False) -> dict[str, str] | None:
    from naas_abi.agents.feature.runtime import check_member

    user = agent_user_id.get()
    workspace = agent_workspace_id.get()
    if not user or not workspace:
        return {"error": "An authenticated workspace session is required."}
    role = check_member(user, workspace)
    if isinstance(role, dict):
        return role
    if write and role not in {"owner", "admin", "member"}:
        return {"error": "Sheets editing requires a workspace writer role."}
    return None


def get_source_control():
    from naas_abi import ABIModule

    return ABIModule.get_instance().engine.services.source_control


def agent_author() -> dict[str, str]:
    name = (agent_user_name.get() or "").strip()
    email = (agent_user_email.get() or "").strip()
    if not name or not email:
        return {}
    return {"author_name": name, "author_email": email}


def repo_id() -> str:
    try:
        from naas_abi.apps.nexus.apps.api.app.core.config import settings

        return settings.coding_repo_id or "abi/monorepo"
    except Exception:  # noqa: BLE001
        return "abi/monorepo"


def ensure_coding_repo() -> str:
    repo = repo_id()
    owner, sep, name = repo.partition("/")
    if not sep or not owner or not name or "/" in name:
        return repo
    try:
        get_source_control().ensure_repo(owner=owner, name=name)
    except SourceControlError:
        pass
    return repo


def _is_repo_id_message(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    rid = repo_id()
    if raw == rid or _REPO_ID_RE.fullmatch(raw):
        return True
    if raw.startswith((f"{rid}:", f"{rid}@")):
        return True
    return raw.endswith(f": {rid}")


def friendly_sc_error(exc: BaseException) -> str:
    text = str(exc).strip() or type(exc).__name__
    lowered = text.lower()
    if any(
        marker in lowered
        for marker in (
            "connection refused",
            "failed to establish",
            "timed out",
            "timeout",
            "connection reset",
            "network is unreachable",
        )
    ):
        return "Forgejo is not reachable. Sheets needs git storage."
    if _is_repo_id_message(text) or "workbook.html" in lowered:
        return _WIPED_WORKBOOK_ERROR
    return text


def tool_error(exc: BaseException) -> dict[str, Any]:
    return {"error": friendly_sc_error(exc)}


def conventional_message(message: str, *, default_type: str = "chore") -> str:
    text = (message or "").strip() or "update sheets workbook"
    if _CONVENTIONAL_COMMIT_RE.match(text):
        return text
    return f"{default_type}(sheets): {text}"


def load_seed_workbook_html(template_id: str | None = None) -> str | None:
    try:
        from importlib import resources

        from naas_abi.agents.sheets.template_resolve import normalize_sheets_template_id

        stem = normalize_sheets_template_id(template_id)
        root = resources.files("naas_abi.apps.nexus.assets.sheets.templates")
        text = (root / f"{stem}.html").read_text(encoding="utf-8")
        return text if text.strip() else None
    except Exception:  # noqa: BLE001
        return None


def seed_workbook_with_title(html: str, title: str) -> str:
    try:
        workbook = parse_workbook_html(html)
        workbook.title = title
        return serialize_workbook_html(workbook, template_html=html)
    except ValueError:
        return html.replace("Sample budget", title, 2)


def _workspace_id() -> str | None:
    value = (agent_workspace_id.get() or "").strip()
    return value or None


def _workspace_segment(workspace_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", workspace_id.strip()).strip("-._")


def branch_name(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"{_BRANCH_PREFIX}{_workspace_segment(ws)}/{slug}"
    return f"{_BRANCH_PREFIX}{slug}"


def _legacy_branch(slug: str) -> str:
    return f"{_BRANCH_PREFIX}{slug}"


def workbook_path(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"sheets/{_workspace_segment(ws)}/{slug}/workbook.html"
    return f"sheets/{slug}/workbook.html"


def _legacy_workbook_path(slug: str) -> str:
    return f"sheets/{slug}/workbook.html"


def project_path(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"sheets/{_workspace_segment(ws)}/{slug}/project.json"
    return f"sheets/{slug}/project.json"


def _legacy_project_path(slug: str) -> str:
    return f"sheets/{slug}/project.json"


def _looks_like_missing_workbook(exc: BaseException, paths: dict[str, str]) -> bool:
    text = str(exc)
    path = paths.get("workbook_path") or ""
    if path and path in text:
        return True
    return _is_repo_id_message(text)


def _display_title(slug: str, stored_title: str | None) -> str:
    for candidate in (stored_title, sheets_active_title.get()):
        text = (candidate or "").strip()
        if text and not is_placeholder_workbook_title(text):
            return text
    derived = derive_workbook_title(sheets_brief.get() or "")
    if derived:
        return derived
    return (
        (stored_title or "").strip()
        or (sheets_active_title.get() or "").strip()
        or slug.replace("-", " ").title()
    )


def _ensure_project_json(
    sc: Any,
    rid: str,
    paths: dict[str, str],
    slug: str,
    *,
    template_id: str | None = None,
) -> str:
    meta: dict[str, Any] = {}
    try:
        existing = sc.get_file(
            repo_id=rid, path=paths["project_path"], ref=paths["branch"]
        )
        if existing.text:
            meta = json.loads(existing.text)
    except (SourceControlError, json.JSONDecodeError, TypeError):
        meta = {}
    stored = str(meta.get("title") or "").strip() if isinstance(meta, dict) else ""
    title = _display_title(slug, stored)
    existing_tid = (
        str(meta.get("template_id") or "").strip() if isinstance(meta, dict) else ""
    )
    resolved_tid = (template_id or "").strip() or existing_tid or "grid-light-v1"
    if (
        isinstance(meta, dict)
        and meta
        and stored == title
        and existing_tid == resolved_tid
    ):
        return title
    ws = _workspace_id()
    payload = {
        **(meta if isinstance(meta, dict) else {}),
        "slug": slug,
        "workspace_id": (meta.get("workspace_id") if isinstance(meta, dict) else "")
        or ws
        or "",
        "title": title,
        "template_id": resolved_tid,
    }
    try:
        sc.upsert_file(
            repo_id=rid,
            path=paths["project_path"],
            content=json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            message=f"chore(sheets): name project {slug}",
            branch=paths["branch"],
            **agent_author(),
        )
    except SourceControlError:
        return stored or title
    sheets_active_title.set(title)
    return title


def resolve_paths(slug: str) -> dict[str, str]:
    ws = _workspace_id()
    sc = get_source_control()
    rid = ensure_coding_repo()
    try:
        names = {b.name for b in sc.list_branches(repo_id=rid)}
    except SourceControlError as exc:
        return {"error": friendly_sc_error(exc)}
    if ws:
        ns_branch = branch_name(slug, ws)
        if ns_branch in names:
            return {
                "branch": ns_branch,
                "workbook_path": workbook_path(slug, ws),
                "project_path": project_path(slug, ws),
            }
    legacy = _legacy_branch(slug)
    if legacy in names:
        if not ws:
            return {"error": f"sheets project {slug} not in this workspace"}
        try:
            meta = sc.get_file(repo_id=rid, path=_legacy_project_path(slug), ref=legacy)
            data = json.loads(meta.text or "{}") if meta.text else {}
            owner = str(data.get("workspace_id") or "").strip()
            if owner != ws:
                return {"error": f"sheets project {slug} not in this workspace"}
        except (SourceControlError, json.JSONDecodeError):
            return {"error": f"sheets project {slug} not in this workspace"}
        return {
            "branch": legacy,
            "workbook_path": _legacy_workbook_path(slug),
            "project_path": _legacy_project_path(slug),
        }
    if ws:
        return {
            "branch": branch_name(slug, ws),
            "workbook_path": workbook_path(slug, ws),
            "project_path": project_path(slug, ws),
        }
    return {
        "branch": legacy,
        "workbook_path": _legacy_workbook_path(slug),
        "project_path": _legacy_project_path(slug),
    }


def ensure_sheets_write_paths(
    slug: str, *, template_id: str | None = None
) -> dict[str, str]:
    paths = resolve_paths(slug)
    if paths.get("error"):
        return paths
    sc = get_source_control()
    rid = ensure_coding_repo()
    try:
        names = {b.name for b in sc.list_branches(repo_id=rid)}
    except SourceControlError as exc:
        return {"error": friendly_sc_error(exc)}
    branch = paths["branch"]
    if branch not in names:
        default = (
            "main" if "main" in names else (next(iter(names)) if names else "main")
        )
        if default not in names:
            return {"error": _WIPED_WORKBOOK_ERROR}
        try:
            sc.create_branch(repo_id=rid, name=branch, from_ref=default)
        except BranchNameConflictError:
            pass
        except SourceControlError as exc:
            return {"error": friendly_sc_error(exc)}
    paths["title"] = _ensure_project_json(sc, rid, paths, slug, template_id=template_id)
    return paths


def _memo_key() -> str:
    user = (agent_user_id.get() or "").strip()
    if not user:
        return ""
    chat = (agent_chat_id.get() or "").strip() or "no-chat"
    return f"{user}:{chat}"


def remember_active_slug(slug: str) -> None:
    key = _memo_key()
    if not key or not slug:
        return
    _ACTIVE_SLUG_MEMO[key] = slug
    _ACTIVE_SLUG_MEMO.move_to_end(key)
    while len(_ACTIVE_SLUG_MEMO) > _ACTIVE_SLUG_MEMO_MAX:
        _ACTIVE_SLUG_MEMO.popitem(last=False)


def _recalled_active_slug() -> str:
    key = _memo_key()
    return _ACTIVE_SLUG_MEMO.get(key, "") if key else ""


def slugify_title(title: str) -> str:
    folded = unicodedata.normalize("NFKD", (title or "").strip().lower())
    raw = "".join(ch for ch in folded if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:60].strip("-")


def unique_slug(base: str, taken: set[str]) -> str:
    if branch_name(base) not in taken and _legacy_branch(base) not in taken:
        return base
    for suffix in range(2, 1000):
        candidate = f"{base}-{suffix}"
        if (
            branch_name(candidate) not in taken
            and _legacy_branch(candidate) not in taken
        ):
            return candidate
    raise SourceControlError("Could not find a free sheets slug")


def resolve_slug(slug: str | None) -> str | dict[str, Any]:
    candidate = (
        (slug or "").strip()
        or (sheets_active_slug.get() or "").strip()
        or _recalled_active_slug()
    )
    if not candidate:
        return {
            "error": (
                "No sheets workbook in context. Open a workbook in Sheets, "
                "or pass slug explicitly."
            )
        }
    if not _SLUG_RE.match(candidate):
        return {"error": "Invalid slug (lowercase kebab-case required)."}
    return candidate


def _sidecar_available() -> bool:
    return bool(coder_workspace_base.get())


def _load_workbook_via_sidecar(slug: str) -> str | dict[str, Any]:
    paths = resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "sidecar"}
    result = _sidecar_call("read_file", {"path": paths["workbook_path"]})
    if result.get("error"):
        return {"error": result["error"], "source": "sidecar"}
    if result.get("binary"):
        return {"error": "Workbook is not UTF-8 text", "source": "sidecar"}
    content = result.get("content")
    if not isinstance(content, str):
        return {"error": "Sidecar read returned no content", "source": "sidecar"}
    return content


def _write_workbook_via_sidecar(slug: str, html: str) -> dict[str, Any]:
    paths = resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "sidecar"}
    result = _sidecar_call(
        "write_file", {"path": paths["workbook_path"], "content": html}
    )
    if result.get("error") or result.get("ok") is False:
        return {
            "error": result.get("error") or "sidecar write failed",
            "source": "sidecar",
        }
    return {
        "ok": True,
        "slug": slug,
        "path": paths["workbook_path"],
        "source": "sidecar",
        "bytes": result.get("bytes"),
    }


def _load_workbook_via_forgejo(slug: str) -> str | dict[str, Any]:
    paths = resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "forgejo"}
    sc = get_source_control()
    try:
        file = sc.get_file(
            repo_id=repo_id(), path=paths["workbook_path"], ref=paths["branch"]
        )
    except SourceControlError as exc:
        if _looks_like_missing_workbook(exc, paths):
            seed = load_seed_workbook_html()
            if seed:
                return seed
            return {"error": _WIPED_WORKBOOK_ERROR, "source": "forgejo"}
        return {"error": friendly_sc_error(exc), "source": "forgejo"}
    if file.is_binary or file.text is None:
        return {"error": "Workbook is not UTF-8 text", "source": "forgejo"}
    return file.text


def _commit_workbook_forgejo(
    slug: str,
    html: str,
    message: str,
    *,
    default_type: str = "chore",
) -> dict[str, Any]:
    paths = resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "forgejo"}
    sc = get_source_control()
    try:
        commit = sc.upsert_file(
            repo_id=repo_id(),
            path=paths["workbook_path"],
            content=html,
            message=conventional_message(message, default_type=default_type),
            branch=paths["branch"],
            **agent_author(),
        )
    except SourceControlError as exc:
        return {"error": friendly_sc_error(exc), "source": "forgejo"}
    return {
        "slug": slug,
        "title": paths.get("title") or slug.replace("-", " ").title(),
        "path": paths["workbook_path"],
        "branch": paths["branch"],
        "commit_sha": commit.sha,
        "message": commit.message,
        "source": "forgejo",
    }


def load_workbook_text(slug: str) -> tuple[str | dict[str, Any], str]:
    denied = require_agent_access()
    if denied:
        return denied, "forgejo"
    return _load_workbook_via_forgejo(slug), "forgejo"


def persist_workbook(
    slug: str,
    html: str,
    message: str,
    *,
    default_type: str = "chore",
) -> dict[str, Any]:
    denied = require_agent_access(write=True)
    if denied:
        return denied
    try:
        result = _commit_workbook_forgejo(
            slug,
            html,
            message,
            default_type=default_type,
        )
        if result.get("error"):
            return result
        result["sources"] = ["forgejo"]
        if _sidecar_available():
            mirror = _write_workbook_via_sidecar(slug, html)
            if mirror.get("ok"):
                result["sources"].append("sidecar")
            else:
                result["sidecar_error"] = mirror.get("error")
        return result
    except Exception as exc:  # noqa: BLE001
        return {"error": friendly_sc_error(exc)}
