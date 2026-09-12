"""DocumentsAgent tools for Nexus Documents projects.

Prefer the Coder workspace sidecar filesystem when a sections runtime is bound
to the request (Continue-parity). Fall back to Forgejo with an explicit note.

Documents live at ``documents/<slug>/document.html`` on branch ``documents/<slug>``. When the
user has a document open in Nexus, ``documents_active_slug`` is set so tools default
to that document and the agent must not ask which document to edit.

Template documents keep section markup in ``<main>`` (~tens of KB) but also ship
inline asset ``<script>`` blobs (~1MB with base64 images). PDF export walks
the live ``.section`` DOM; tools therefore:

- expose section-scoped read/write and surgical string replace
- redact heavy scripts / data-URLs on full-document reads
- never require the model to edit ``buildPptx`` or ``FOOTER_TXT``
"""

from __future__ import annotations

import html as html_lib
import json
import re
import unicodedata
from collections import OrderedDict
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.documents import (
    auto_document_title,
    derive_document_title,
    is_placeholder_document_title,
    note_documents_list,
    note_documents_section_read,
    reject_documents_section_read,
    reject_read_document,
    reject_repeat_list_document_sections,
    reject_repeat_apply_document_commands,
    reject_replace_in_document_on_fill,
    reject_unresearched_documents_write,
    resolve_document_title,
)
from naas_abi_core.services.agent.context import (
    agent_chat_id,
    agent_user_email,
    agent_user_id,
    agent_user_name,
    agent_workspace_id,
    coder_workspace_base,
    documents_active_mode,
    documents_active_slug,
    documents_active_title,
    documents_brief,
    note_documents_write,
)
from naas_abi_core.services.agent.tools.workspace_tools import _call as _sidecar_call
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    SourceControlError,
)

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BRANCH_PREFIX = "documents/"
_DATA_URL_RE = re.compile(
    r"data:image/[a-zA-Z0-9.+-]+;base64,[A-Za-z0-9+/=\s]+",
    re.IGNORECASE,
)
_SCRIPT_RE = re.compile(r"<script\b[^>]*>.*?</script>", re.IGNORECASE | re.DOTALL)
_MAIN_RE = re.compile(r"(<main\b[^>]*>)(.*?)(</main>)", re.IGNORECASE | re.DOTALL)
_SECTION_SPLIT_RE = re.compile(r"(?=<section\b)", re.IGNORECASE)
_SECTION_OPEN_RE = re.compile(r"<section\b([^>]*)>", re.IGNORECASE)
_ATTR_ID_RE = re.compile(r"""\bid\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_ATTR_CLASS_RE = re.compile(r"""\bclass\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_H1_RE = re.compile(r"<h1\b[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_H2_RE = re.compile(r"<h2\b[^>]*>(.*?)</h2>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")
_REDACTED_PLACEHOLDER = "[REDACTED_DATA_URL]"
_SCRIPT_PLACEHOLDER = "<!-- REDACTED_SCRIPT -->"
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_WIPED_DECK_ERROR = "API restart wiped this document. Click New, then retry."


def _get_source_control():
    from naas_abi import ABIModule

    return ABIModule.get_instance().engine.services.source_control


def _agent_author() -> dict[str, str]:
    """git author kwargs for the connected user, when the request boundary set
    them (see agent.context). Adapters accept a plain name/email pair on the
    commit's author/committer fields directly — no linked Forgejo account
    required — so an Abi-driven commit attributes to the person who asked for
    it instead of the service account, same as the REST endpoints that write
    on the user's behalf (see sections FastAPI adapter's `author_name`/
    `author_email`). Empty when either half is unset, so upsert_file falls
    back to its own default identity rather than sending a half author.
    """
    name = (agent_user_name.get() or "").strip()
    email = (agent_user_email.get() or "").strip()
    if not name or not email:
        return {}
    return {"author_name": name, "author_email": email}


def _repo_id() -> str:
    try:
        from naas_abi.apps.nexus.apps.api.app.core.config import settings

        return settings.coding_repo_id or "abi/monorepo"
    except Exception:  # noqa: BLE001
        return "abi/monorepo"


def _ensure_coding_repo() -> str:
    """Seed CODING_REPO_ID. Local in_memory starts empty; UI create already does this."""
    repo_id = _repo_id()
    owner, sep, name = repo_id.partition("/")
    if not sep or not owner or not name or "/" in name:
        return repo_id
    try:
        _get_source_control().ensure_repo(owner=owner, name=name)
    except SourceControlError:
        pass
    return repo_id


def _is_repo_id_message(text: str) -> bool:
    raw = (text or "").strip()
    if not raw:
        return False
    repo_id = _repo_id()
    if raw == repo_id or _REPO_ID_RE.fullmatch(raw):
        return True
    if raw.startswith((f"{repo_id}:", f"{repo_id}@")):
        return True
    return raw.endswith(f": {repo_id}")


def _friendly_sc_error(exc: BaseException) -> str:
    """Never return a raw owner/name (InMemory RepoNotFoundError)."""
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
        return "Forgejo is not reachable. Documents needs git storage."
    if _is_repo_id_message(text) or "document.html" in lowered:
        return _WIPED_DECK_ERROR
    return text


def _tool_error(exc: BaseException) -> dict[str, Any]:
    return {"error": _friendly_sc_error(exc)}


_CONVENTIONAL_COMMIT_RE = re.compile(
    r"^(feat|fix|chore|style|refactor|docs|perf)(\([a-z0-9_.-]+\))?!?: .+"
)


def _conventional_message(message: str, *, default_type: str = "chore") -> str:
    """Coerce a commit message into Conventional Commits so `sections_history`
    and Forgejo log a real changelog instead of free text per tool call.

    ``default_type`` should reflect what the *calling tool* does (feat for
    additions like insert/duplicate section, fix for corrections like
    replace_in_document, refactor for restructuring, style for reordering)
    so an LLM-authored free-text message (no ``type(scope):`` prefix of its
    own) still lands in the semver bucket the edit actually belongs to,
    instead of the non-bumping "chore" default. A document has no public API, so
    there is no "breaking change" concept here: `_semver_from_commits` keeps
    major pinned at 0 and treats a `!` breaking marker the same as `feat`
    (bump minor) — nothing in this module needs to detect breaking changes.
    """
    text = (message or "").strip() or "update sections document"
    if _CONVENTIONAL_COMMIT_RE.match(text):
        return text
    return f"{default_type}(sections): {text}"


def _load_seed_document_html() -> str | None:
    """Same Article Light seed the UI New path writes."""
    try:
        from importlib import resources

        root = resources.files("naas_abi.apps.nexus.assets.documents.templates")
        text = (root / "article-light-v1.html").read_text(encoding="utf-8")
        return text if text.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _looks_like_missing_document(exc: BaseException, paths: dict[str, str]) -> bool:
    text = str(exc)
    document = paths.get("document_path") or ""
    if document and document in text:
        return True
    return _is_repo_id_message(text)


def _display_title(slug: str, stored_title: str | None) -> str:
    """Best display title for a document, naming it after the brief when untitled.

    A document created by the UI New button is stored as "Untitled document".
    The first agent write is the moment we know what it is about, so adopt the
    topic of the brief then. A title the user (or an earlier turn) already
    chose is never overwritten.
    """
    for candidate in (stored_title, documents_active_title.get()):
        text = (candidate or "").strip()
        if text and not is_placeholder_document_title(text):
            return text
    derived = derive_document_title(documents_brief.get() or "")
    if derived:
        return derived
    return (
        (stored_title or "").strip()
        or (documents_active_title.get() or "").strip()
        or slug.replace("-", " ").title()
    )


def _ensure_project_json(
    sc: Any, repo_id: str, paths: dict[str, str], slug: str
) -> str:
    """Seed (or retitle) project.json. Returns the document's display title.

    Preview GET resolves the project via project.json, and the sidebar tree
    reads its title, so writes must keep it current.
    """
    meta: dict[str, Any] = {}
    try:
        existing = sc.get_file(
            repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        )
        if existing.text:
            meta = json.loads(existing.text)
    except (SourceControlError, json.JSONDecodeError, TypeError):
        meta = {}
    stored = str(meta.get("title") or "").strip() if isinstance(meta, dict) else ""
    title = _display_title(slug, stored)
    if isinstance(meta, dict) and meta and stored == title:
        return title
    ws = _workspace_id()
    payload = {
        **(meta if isinstance(meta, dict) else {}),
        "slug": slug,
        "workspace_id": (meta.get("workspace_id") if isinstance(meta, dict) else "")
        or ws
        or "",
        "title": title,
        "template_id": (
            (meta.get("template_id") if isinstance(meta, dict) else "")
            or "minimal-light-v1"
        ),
    }
    try:
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["project_path"],
            content=json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
            message=f"chore(sections): name project {slug}",
            branch=paths["branch"],
            **_agent_author(),
        )
    except SourceControlError:
        return stored or title
    # Later tools in this turn (and the open_document note) report the new name.
    documents_active_title.set(title)
    return title


def _ensure_sections_write_paths(slug: str) -> dict[str, str]:
    """Repo + sections branch + project.json, matching the UI create path."""
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return paths
    sc = _get_source_control()
    repo_id = _ensure_coding_repo()
    try:
        names = {b.name for b in sc.list_branches(repo_id=repo_id)}
    except SourceControlError as exc:
        return {"error": _friendly_sc_error(exc)}
    branch = paths["branch"]
    if branch not in names:
        default = "main" if "main" in names else (next(iter(names)) if names else "main")
        if default not in names:
            return {"error": _WIPED_DECK_ERROR}
        try:
            sc.create_branch(repo_id=repo_id, name=branch, from_ref=default)
        except BranchNameConflictError:
            pass
        except SourceControlError as exc:
            return {"error": _friendly_sc_error(exc)}
    paths["title"] = _ensure_project_json(sc, repo_id, paths, slug)
    return paths


# LangChain runs each tool in an isolated context, so a ContextVar set inside
# create_documents_project is invisible to the next tool call. Remember the document
# Abi just created per (user, conversation) instead, and let _resolve_slug fall
# back to it. Bounded so a long-lived API process cannot grow without limit.
_ACTIVE_SLUG_MEMO: OrderedDict[str, str] = OrderedDict()
_ACTIVE_SLUG_MEMO_MAX = 256


def _memo_key() -> str:
    user = (agent_user_id.get() or "").strip()
    if not user:
        return ""
    chat = (agent_chat_id.get() or "").strip() or "no-chat"
    return f"{user}:{chat}"


def _remember_active_slug(slug: str) -> None:
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


def _forget_active_slugs() -> None:
    _ACTIVE_SLUG_MEMO.clear()


def _slugify_title(title: str) -> str:
    """Kebab-case slug from a human title, matching the UI create path.

    Accents fold to ASCII so a French title gives a readable URL
    ("Matériaux de construction" -> ``materiaux-de-construction``) instead of
    dropping the accented letters.
    """
    folded = unicodedata.normalize("NFKD", (title or "").strip().lower())
    raw = "".join(ch for ch in folded if not unicodedata.combining(ch))
    slug = re.sub(r"[^a-z0-9]+", "-", raw).strip("-")
    return slug[:60].strip("-")


def _unique_slug(base: str, taken: set[str]) -> str:
    """First free ``base``, ``base-2``, ``base-3`` … against existing branches."""
    if _branch(base) not in taken and _legacy_branch(base) not in taken:
        return base
    for suffix in range(2, 1000):
        candidate = f"{base}-{suffix}"
        if _branch(candidate) not in taken and _legacy_branch(candidate) not in taken:
            return candidate
    raise SourceControlError("Could not find a free sections slug")


def _seed_document_with_title(html: str, title: str) -> str:
    """Put the requested title on the cover so the document opens named correctly."""
    for placeholder in ("Document Title", "Presentation Title"):
        applied = _apply_replacements(html, placeholder, title, 0)
        if not isinstance(applied, dict):
            return applied[0]
    return html


def _workspace_id() -> str | None:
    value = (agent_workspace_id.get() or "").strip()
    return value or None


def _workspace_segment(workspace_id: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", workspace_id.strip()).strip("-._")


def _branch(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"{_BRANCH_PREFIX}{_workspace_segment(ws)}/{slug}"
    return f"{_BRANCH_PREFIX}{slug}"


def _legacy_branch(slug: str) -> str:
    return f"{_BRANCH_PREFIX}{slug}"


def _document_path(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"documents/{_workspace_segment(ws)}/{slug}/document.html"
    return f"documents/{slug}/document.html"


def _legacy_document_path(slug: str) -> str:
    return f"documents/{slug}/document.html"


def _project_path(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"documents/{_workspace_segment(ws)}/{slug}/project.json"
    return f"documents/{slug}/project.json"


def _legacy_project_path(slug: str) -> str:
    return f"documents/{slug}/project.json"


def _resolve_paths(slug: str) -> dict[str, str]:
    """Prefer namespaced paths; fall back to legacy when that branch exists."""
    ws = _workspace_id()
    sc = _get_source_control()
    repo_id = _ensure_coding_repo()
    try:
        names = {b.name for b in sc.list_branches(repo_id=repo_id)}
    except SourceControlError as exc:
        return {"error": _friendly_sc_error(exc)}
    if ws:
        ns_branch = _branch(slug, ws)
        if ns_branch in names:
            return {
                "branch": ns_branch,
                "document_path": _document_path(slug, ws),
                "project_path": _project_path(slug, ws),
            }
    legacy = _legacy_branch(slug)
    if legacy in names:
        # Fail closed: legacy documents require a verified matching owner.
        if not ws:
            return {"error": f"sections project {slug} not in this workspace"}
        try:
            meta = sc.get_file(
                repo_id=repo_id, path=_legacy_project_path(slug), ref=legacy
            )
            data = json.loads(meta.text or "{}") if meta.text else {}
            owner = str(data.get("workspace_id") or "").strip()
            if owner != ws:
                return {"error": f"sections project {slug} not in this workspace"}
        except (SourceControlError, json.JSONDecodeError):
            return {"error": f"sections project {slug} not in this workspace"}
        return {
            "branch": legacy,
            "document_path": _legacy_document_path(slug),
            "project_path": _legacy_project_path(slug),
        }
    if ws:
        # Default to namespaced location for new writes.
        return {
            "branch": _branch(slug, ws),
            "document_path": _document_path(slug, ws),
            "project_path": _project_path(slug, ws),
        }
    return {
        "branch": legacy,
        "document_path": _legacy_document_path(slug),
        "project_path": _legacy_project_path(slug),
    }


def _resolve_slug(slug: str | None) -> str | dict[str, Any]:
    """Prefer explicit slug; else the open document from pane context."""
    candidate = (
        (slug or "").strip()
        or (documents_active_slug.get() or "").strip()
        or _recalled_active_slug()
    )
    if not candidate:
        return {
            "error": (
                "No sections document in context. Open a document in Documents, "
                "or pass slug explicitly."
            )
        }
    if not _SLUG_RE.match(candidate):
        return {"error": "Invalid slug (lowercase kebab-case required)."}
    return candidate


def _open_document_note(slug: str) -> dict[str, Any]:
    title = documents_active_title.get()
    mode = documents_active_mode.get()
    note: dict[str, Any] = {
        "open_document": {
            "slug": slug,
            "path": _document_path(slug),
            "branch": _branch(slug),
        }
    }
    if title:
        note["open_document"]["title"] = title
    if mode:
        note["open_document"]["mode"] = mode
    return note


def _sidecar_available() -> bool:
    return bool(coder_workspace_base.get())


def _load_document_via_sidecar(slug: str) -> str | dict[str, Any]:
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "sidecar"}
    result = _sidecar_call("read_file", {"path": paths["document_path"]})
    if result.get("error"):
        return {"error": result["error"], "source": "sidecar"}
    if result.get("binary"):
        return {"error": "Document is not UTF-8 text", "source": "sidecar"}
    content = result.get("content")
    if not isinstance(content, str):
        return {"error": "Sidecar read returned no content", "source": "sidecar"}
    return content


def _write_document_via_sidecar(slug: str, html: str) -> dict[str, Any]:
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "sidecar"}
    result = _sidecar_call(
        "write_file", {"path": paths["document_path"], "content": html}
    )
    if result.get("error") or result.get("ok") is False:
        return {
            "error": result.get("error") or "sidecar write failed",
            "source": "sidecar",
        }
    return {
        "ok": True,
        "slug": slug,
        "path": paths["document_path"],
        "source": "sidecar",
        "bytes": result.get("bytes"),
    }


def _load_document_via_forgejo(slug: str) -> str | dict[str, Any]:
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "forgejo"}
    sc = _get_source_control()
    try:
        file = sc.get_file(
            repo_id=_repo_id(), path=paths["document_path"], ref=paths["branch"]
        )
    except SourceControlError as exc:
        if _looks_like_missing_document(exc, paths):
            seed = _load_seed_document_html()
            if seed:
                return seed
            return {"error": _WIPED_DECK_ERROR, "source": "forgejo"}
        return {"error": _friendly_sc_error(exc), "source": "forgejo"}
    if file.is_binary or file.text is None:
        return {"error": "Document is not UTF-8 text", "source": "forgejo"}
    return file.text


def _commit_document_forgejo(
    slug: str, html: str, message: str, *, default_type: str = "chore"
) -> dict[str, Any]:
    paths = _ensure_sections_write_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "forgejo"}
    sc = _get_source_control()
    try:
        commit = sc.upsert_file(
            repo_id=_repo_id(),
            path=paths["document_path"],
            content=html,
            message=_conventional_message(message, default_type=default_type),
            branch=paths["branch"],
            **_agent_author(),
        )
    except SourceControlError as exc:
        return {"error": _friendly_sc_error(exc), "source": "forgejo"}
    return {
        "slug": slug,
        # The chat document card labels itself from this.
        "title": paths.get("title") or slug.replace("-", " ").title(),
        "path": paths["document_path"],
        "branch": paths["branch"],
        "commit_sha": commit.sha,
        "message": commit.message,
        "source": "forgejo",
    }


def _load_document_text(slug: str) -> tuple[str | dict[str, Any], str]:
    """Load document HTML. Returns (html_or_error, source). Prefer sidecar."""
    if _sidecar_available():
        loaded = _load_document_via_sidecar(slug)
        if isinstance(loaded, str):
            return loaded, "sidecar"
        # Fall through to Forgejo when sidecar is bound but read failed.
        forgejo = _load_document_via_forgejo(slug)
        if isinstance(forgejo, str):
            return forgejo, "forgejo-fallback"
        return loaded, "sidecar"
    forgejo = _load_document_via_forgejo(slug)
    if isinstance(forgejo, str):
        return forgejo, "forgejo"
    return forgejo, "forgejo"


def _persist_document(
    slug: str, html: str, message: str, *, default_type: str = "chore"
) -> dict[str, Any]:
    """Write editing context (sidecar) then version storage (Forgejo).

    Product truth when the sections runtime is up: Coder/sidecar is the live
    editing copy. Forgejo is the commit/history snapshot (Save + dual-write).

    ``default_type`` is the Conventional Commits type this *tool* implies
    (feat for additions, fix/refactor for edits, ...) — used only when
    ``message`` is free text without its own ``type(scope):`` prefix, so an
    LLM-authored descriptive message (e.g. "Update event date on cover
    section") still buckets into the right semver bump instead of always
    falling back to the non-bumping "chore" type.
    """
    from naas_abi.agents.tools.documents_commands import (
        leftover_write_note,
        normalize_document_flow,
    )

    html = normalize_document_flow(html)

    def _with_leftovers(payload: dict[str, Any]) -> dict[str, Any]:
        if payload.get("error"):
            return payload
        payload.update(leftover_write_note(html))
        return payload
    sources: list[str] = []
    sidecar_result: dict[str, Any] | None = None
    if _sidecar_available():
        sidecar_result = _write_document_via_sidecar(slug, html)
        if sidecar_result.get("ok"):
            sources.append("sidecar")
        else:
            # Keep going: Forgejo write still updates version storage.
            sources.append("sidecar-failed")
    try:
        forgejo = _commit_document_forgejo(slug, html, message, default_type=default_type)
        if forgejo.get("error"):
            if sidecar_result and sidecar_result.get("ok"):
                return _with_leftovers(
                    {
                        **sidecar_result,
                        "sources": sources,
                        "forgejo_error": forgejo.get("error"),
                        "note": (
                            "Updated Coder workspace (live edit); Forgejo snapshot failed. "
                            "Preview should follow sidecar. Use File → Save later for history."
                        ),
                    }
                )
            return {**forgejo, "sources": sources}
        sources.append("forgejo")
        result = {**forgejo, "sources": sources}
        if sidecar_result and not sidecar_result.get("ok"):
            result["sidecar_error"] = sidecar_result.get("error")
            result["note"] = (
                "Wrote git snapshot only; Coder sidecar write failed. "
                "Preview should refresh from the git copy."
            )
        elif "sidecar" in sources:
            result["note"] = (
                "Updated Coder workspace (live edit) and committed Forgejo snapshot."
            )
        return _with_leftovers(result)
    except Exception as exc:  # noqa: BLE001
        if sidecar_result and sidecar_result.get("ok"):
            return _with_leftovers(
                {
                    **sidecar_result,
                    "sources": sources,
                    "forgejo_error": _friendly_sc_error(exc),
                    "note": (
                        "Updated Coder workspace (live edit); Forgejo snapshot failed. "
                        "Preview should follow sidecar. Use File → Save later for history."
                    ),
                }
            )
        return {"error": _friendly_sc_error(exc), "sources": sources}


def _replace_string_pairs(old: str, new: str) -> list[tuple[str, str]]:
    """Return (old, new) pairs covering plain text and HTML-entity forms.

    Cover titles in document HTML use ``&amp;`` while PDF script strings use raw
    ``&``. A user (or Abi) almost always types the visible form with ``&``.
    """
    pairs: list[tuple[str, str]] = [(old, new)]
    old_esc = html_lib.escape(old, quote=False)
    new_esc = html_lib.escape(new, quote=False)
    if old_esc != old:
        pairs.append((old_esc, new_esc))
    old_un = html_lib.unescape(old)
    new_un = html_lib.unescape(new)
    if old_un != old:
        pairs.append((old_un, new_un))
        old_un_esc = html_lib.escape(old_un, quote=False)
        new_un_esc = html_lib.escape(new_un, quote=False)
        if old_un_esc != old_un:
            pairs.append((old_un_esc, new_un_esc))
    seen: set[tuple[str, str]] = set()
    out: list[tuple[str, str]] = []
    for pair in pairs:
        if not pair[0] or pair in seen:
            continue
        seen.add(pair)
        out.append(pair)
    return out


def _char_entity_alts(ch: str) -> str:
    """Regex alternation matching a char and common HTML entity spellings."""
    if ch == "&":
        return r"(?:&|&amp;)"
    code = ord(ch)
    alts = [re.escape(ch)]
    name = html_lib.entities.codepoint2name.get(code)
    if name:
        alts.append(re.escape(f"&{name};"))
    # Decimal + hex numeric character references (optional leading zeros).
    alts.append(rf"&#0*{code};")
    alts.append(rf"&#x0*{code:x};")
    alts.append(rf"&#X0*{code:X};")
    if len(alts) == 1:
        return alts[0]
    return "(?:" + "|".join(alts) + ")"


def _entity_flex_pattern(plain: str) -> re.Pattern[str]:
    """Compile a regex where ``&``, dashes, and other entity-prone chars flex.

    Searching for ``—`` or ``&mdash;`` (after unescape) must match document HTML
    that stores ``&mdash;``, ``&#8212;``, or the literal Unicode dash. Same for
    ``&`` / ``&amp;`` so cover ``<h1>`` text updates with PDF script strings.
    """
    parts: list[str] = []
    i = 0
    while i < len(plain):
        if plain.startswith("&amp;", i):
            parts.append(r"(?:&|&amp;)")
            i += 5
            continue
        ch = plain[i]
        # Flex entity-prone characters: ampersand, markup escapes, and any
        # non-ASCII / named-entity codepoint (mdash, ndash, nbsp, quotes, …).
        name = html_lib.entities.codepoint2name.get(ord(ch))
        if ch == "&" or ch in "<>\"'" or name or ord(ch) > 127:
            parts.append(_char_entity_alts(ch))
        else:
            parts.append(re.escape(ch))
        i += 1
    return re.compile("".join(parts))


# Back-compat alias used by older imports / notebooks.
_amp_flex_pattern = _entity_flex_pattern


def _mirror_amp_encoding(matched: str, new_plain: str) -> str:
    """Keep ``&amp;`` in HTML regions and raw ``&`` in script string regions."""
    if "&amp;" in matched:
        return html_lib.escape(new_plain, quote=False)
    return new_plain


def _cover_h1_text(html: str) -> str | None:
    """Visible cover title: first section ``<h1>``, else first document ``<h1>``."""
    _prefix, sections, _suffix = _split_sections(html)
    target = sections[0] if sections else html
    match = _H1_RE.search(target)
    if not match:
        return None
    return html_lib.unescape(_strip_tags(match.group(1)))


_COVER_SUBTITLE_RE = re.compile(
    r'<p\b[^>]*class=["\'][^"\']*\bsubtitle\b[^"\']*["\'][^>]*>(.*?)</p>',
    re.IGNORECASE | re.DOTALL,
)


def _cover_subtitle_text(html: str) -> str | None:
    """Visible cover subtitle: first ``p.subtitle`` in the cover section."""
    _prefix, sections, _suffix = _split_sections(html)
    target = sections[0] if sections else html
    match = _COVER_SUBTITLE_RE.search(target)
    if not match:
        return None
    return html_lib.unescape(_strip_tags(match.group(1)))


def _apply_replacements(
    html: str, old: str, new: str, occurrence: int
) -> tuple[str, int, int] | dict[str, Any]:
    """Apply surgical replace across plain + entity variants.

    ``&`` in ``old`` matches both literal ``&`` and ``&amp;``; em/en dashes
    match ``—`` / ``&mdash;`` / ``&#8212;`` (and ndash forms) so cover
    subtitles update when Abi searches either spelling.

    Returns ``(updated_html, matches_found, replacements)`` or an error dict.
    """
    if occurrence < 0:
        return {"error": "occurrence must be >= 0 (0 = all)"}
    if not old:
        return {"error": "old must be a non-empty string"}

    old_plain = html_lib.unescape(old)
    new_plain = html_lib.unescape(new)
    pattern = _entity_flex_pattern(old_plain)
    matches: list[tuple[int, int, str]] = [
        (m.start(), m.end(), _mirror_amp_encoding(m.group(0), new_plain))
        for m in pattern.finditer(html)
    ]
    count = len(matches)
    if count == 0:
        return {
            "error": "old string not found in document",
            "hint": (
                "Try read_document for the heading outline, then "
                "replace_in_document with the exact visible text (tools also "
                "match HTML entities like &amp;, &mdash;, &#8212;). For "
                "cover/title edits on the first heading, pass section_index=0."
            ),
        }
    if occurrence == 0:
        selected = matches
    else:
        if occurrence > count:
            return {
                "error": f"occurrence {occurrence} out of range ({count} match(es))"
            }
        selected = [matches[occurrence - 1]]
    updated = html
    # Apply from the end so earlier offsets stay valid.
    for start, end, replacement in sorted(selected, key=lambda m: m[0], reverse=True):
        updated = updated[:start] + replacement + updated[end:]
    return updated, count, len(selected)


def _apply_replacements_in_section(
    html: str,
    old: str,
    new: str,
    occurrence: int,
    *,
    section_index: int | None = None,
    section_id: str | None = None,
) -> tuple[str, int, int, int] | dict[str, Any]:
    """Replace within one ``<section>`` when scoped; else whole document.

    Returns ``(updated_html, matches_found, replacements, resolved_section_index)``
    or an error dict. ``resolved_section_index`` is ``-1`` when unscoped.
    """
    if section_index is None and not section_id:
        applied = _apply_replacements(html, old, new, occurrence)
        if isinstance(applied, dict):
            return applied
        updated, found, replaced = applied
        return updated, found, replaced, -1

    prefix, sections, suffix = _split_sections(html)
    if not sections:
        return {
            "error": "Document has no <section> sections to scope the replace into.",
            "hint": "Omit section_index/section_id to replace across the whole document.",
        }
    resolved_idx = _resolve_section_index(sections, section_index, section_id)
    if isinstance(resolved_idx, dict):
        return resolved_idx
    applied = _apply_replacements(sections[resolved_idx], old, new, occurrence)
    if isinstance(applied, dict):
        return applied
    section_updated, found, replaced = applied
    sections[resolved_idx] = section_updated
    return prefix + "".join(sections) + suffix, found, replaced, resolved_idx


def _redact_data_urls(html: str) -> tuple[str, int]:
    count = 0

    def _sub(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return _REDACTED_PLACEHOLDER

    return _DATA_URL_RE.sub(_sub, html), count


def _redact_scripts(html: str) -> tuple[str, int]:
    count = 0

    def _sub(_match: re.Match[str]) -> str:
        nonlocal count
        count += 1
        return _SCRIPT_PLACEHOLDER

    return _SCRIPT_RE.sub(_sub, html), count


def _strip_tags(text: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", text)).strip()


def _main_regions(html: str) -> tuple[str, str, str] | None:
    match = _MAIN_RE.search(html)
    if not match:
        return None
    before = html[: match.start()] + match.group(1)
    inner = match.group(2)
    after = match.group(3) + html[match.end() :]
    return before, inner, after


def _split_sections(html: str) -> tuple[str, list[str], str]:
    """Split document HTML into prefix, ``<section>`` blocks (inside main), suffix.

    Heavy post-``</main>`` scripts stay in suffix and are never returned by
    section reads.
    """
    regions = _main_regions(html)
    if regions is None:
        parts = _SECTION_SPLIT_RE.split(html)
        if len(parts) <= 1:
            return html, [], ""
        prefix = parts[0]
        sections = [p for p in parts[1:] if p.lstrip().lower().startswith("<section")]
        trimmed: list[str] = []
        for sec in sections:
            close = sec.lower().find("</section>")
            trimmed.append(sec if close < 0 else sec[: close + len("</section>")])
        return prefix, trimmed, ""

    before, inner, after = regions
    parts = _SECTION_SPLIT_RE.split(inner)
    if len(parts) <= 1:
        return before + inner, [], after

    lead = parts[0]
    sections, inter_suffix = _attach_inter_section_markup(parts[1:])
    return before + lead, sections, inter_suffix + after


def _join_sections(prefix: str, sections: list[str], suffix: str) -> str:
    """Inverse of ``_split_sections``: prefix + sections + suffix."""
    return prefix + "".join(sections) + suffix


_ATTR_LAYOUT_RE = re.compile(r"""\bdata-layout\s*=\s*["']([^"']+)["']""", re.IGNORECASE)
_DIVIDER_TITLE_RE = re.compile(
    r"""<div\b[^>]*class=["'][^"']*\bdivider-title\b[^"']*["'][^>]*>(.*?)</div>""",
    re.IGNORECASE | re.DOTALL,
)
_DEFAULT_INSERT_TITLE = "Heading"
_LAYOUT_ALIASES = {
    "blank": "content",
    "divider": "section-divider",
    "section": "section-divider",
    "page": "page-break",
    "pagebreak": "page-break",
}
_KNOWN_LAYOUTS = frozenset({"cover", "section-divider", "content", "page-break"})
_LAYOUT_SKELETONS = {
    "cover": (
        '<section class="page cover" data-layout="cover">'
        "<h1>{title}</h1>"
        '<p class="deck">A one-line summary the reader can scan before the body.</p>'
        "</section>"
    ),
    "section-divider": (
        '<section class="page" data-layout="section-divider">'
        "<h2>{title}</h2>"
        "</section>"
    ),
    "content": (
        '<section class="page" data-layout="content">'
        "<h2>{title}</h2>"
        "<p></p>"
        "</section>"
    ),
    "page-break": (
        '<section class="page" data-layout="page-break">'
        '<div class="page-break" data-nexus-page-break></div>'
        "<h2>{title}</h2>"
        "<p></p>"
        "</section>"
    ),
}


def _attach_inter_section_markup(section_parts: list[str]) -> tuple[list[str], str]:
    sections: list[str] = []
    trailing_after_last = ""
    for i, part in enumerate(section_parts):
        if not part.lstrip().lower().startswith("<section"):
            if sections:
                sections[-1] += part
            continue
        close = part.lower().find("</section>")
        if close < 0:
            sections.append(part)
            continue
        end = close + len("</section>")
        sections.append(part[:end])
        rest = part[end:]
        if i == len(section_parts) - 1:
            trailing_after_last = rest
        elif rest:
            sections[-1] += rest
    return sections, trailing_after_last


def _section_meta(index: int, section_html: str) -> dict[str, Any]:
    open_m = _SECTION_OPEN_RE.search(section_html)
    attrs = open_m.group(1) if open_m else ""
    id_m = _ATTR_ID_RE.search(attrs)
    class_m = _ATTR_CLASS_RE.search(attrs)
    h1_m = _H1_RE.search(section_html)
    title = _strip_tags(h1_m.group(1)) if h1_m else ""
    if not title:
        divider_m = _DIVIDER_TITLE_RE.search(section_html)
        title = _strip_tags(divider_m.group(1)) if divider_m else ""
    if not title:
        h2_m = _H2_RE.search(section_html)
        title = _strip_tags(h2_m.group(1)) if h2_m else ""
    redacted, n_assets = _redact_data_urls(section_html)
    return {
        "index": index,
        "id": id_m.group(1) if id_m else None,
        "class": class_m.group(1) if class_m else None,
        "title": title,
        "chars": len(section_html),
        "chars_redacted": len(redacted),
        "redacted_assets": n_assets,
    }


def _resolve_section_index(
    sections: list[str], index: int | None, section_id: str | None
) -> int | dict[str, str]:
    if section_id:
        wanted = section_id.strip()
        for i, sec in enumerate(sections):
            open_m = _SECTION_OPEN_RE.search(sec)
            attrs = open_m.group(1) if open_m else ""
            id_m = _ATTR_ID_RE.search(attrs)
            if id_m and id_m.group(1) == wanted:
                return i
        return {"error": f"No section with id={wanted!r}"}
    if index is None:
        return {"error": "Provide index or section_id"}
    if index < 0 or index >= len(sections):
        return {
            "error": f"index out of range (0..{max(0, len(sections) - 1)}; got {index})"
        }
    return index


def _parse_section_writes(raw: Any) -> list[dict[str, Any]] | dict[str, str]:
    """Parse write_document_sections payload: JSON array or already-decoded list."""
    payload = raw
    if isinstance(raw, str):
        text = raw.strip()
        if not text:
            return {"error": "sections must be a non-empty JSON array"}
        try:
            payload = json.loads(text)
        except json.JSONDecodeError as exc:
            return {"error": f"sections is not valid JSON: {exc}"}
    if not isinstance(payload, list) or not payload:
        return {"error": "sections must be a non-empty JSON array of {index or section_id, html}"}
    parsed: list[dict[str, Any]] = []
    for i, item in enumerate(payload):
        if not isinstance(item, dict):
            return {"error": f"sections[{i}] must be an object with html and index or section_id"}
        html = item.get("html")
        if not isinstance(html, str) or not html.strip():
            return {"error": f"sections[{i}].html must be a non-empty string"}
        if "<section" not in html.lower():
            return {"error": f"sections[{i}].html must include a <section>...</section> block"}
        index = item.get("index")
        section_id = item.get("section_id") or item.get("id")
        if index is None and not section_id:
            return {"error": f"sections[{i}] needs index or section_id"}
        if index is not None:
            try:
                index = int(index)
            except (TypeError, ValueError):
                return {"error": f"sections[{i}].index must be an integer"}
        parsed.append(
            {
                "html": html,
                "index": index,
                "section_id": str(section_id).strip() if section_id else None,
            }
        )
    return parsed


def _apply_section_writes(
    original: str,
    items: list[dict[str, Any]],
) -> tuple[str, list[int]] | dict[str, str]:
    """Replace several sections in one pass. Returns (html, written indexes)."""
    prefix, sections, suffix = _split_sections(original)
    written: list[int] = []
    for item in items:
        resolved_idx = _resolve_section_index(
            sections, item.get("index"), item.get("section_id")
        )
        if isinstance(resolved_idx, dict):
            return resolved_idx
        sections[resolved_idx] = _restore_redacted_data_urls(
            str(item["html"]).strip(), sections[resolved_idx]
        )
        written.append(resolved_idx)
    new_html = _join_sections(prefix, sections, suffix)
    if _MAIN_RE.search(original) and not _MAIN_RE.search(new_html):
        return {"error": "Refusing to write: reconstructed HTML lost <main>."}
    return new_html, written


def _section_id(section_html: str) -> str | None:
    open_m = _SECTION_OPEN_RE.search(section_html)
    attrs = open_m.group(1) if open_m else ""
    id_m = _ATTR_ID_RE.search(attrs)
    return id_m.group(1) if id_m else None


def _normalize_layout(layout: str) -> str | dict[str, str]:
    name = (layout or "content").strip().lower() or "content"
    name = _LAYOUT_ALIASES.get(name, name)
    if name not in _KNOWN_LAYOUTS:
        return {
            "error": (
                f"Unknown layout {layout!r}. Use cover, section-divider, content, or page-break."
            )
        }
    return name


def _section_layout(section_html: str) -> str:
    open_m = _SECTION_OPEN_RE.search(section_html)
    attrs = open_m.group(1) if open_m else ""
    layout_m = _ATTR_LAYOUT_RE.search(attrs)
    if layout_m:
        raw = layout_m.group(1).strip().lower()
        aliased = _LAYOUT_ALIASES.get(raw, raw)
        if aliased in _KNOWN_LAYOUTS:
            return aliased
    class_m = _ATTR_CLASS_RE.search(attrs)
    classes = (class_m.group(1) if class_m else "").lower().split()
    if "cover" in classes:
        return "cover"
    if "section-divider" in classes:
        return "section-divider"
    return "content"


def _find_layout_donor(sections: list[str], layout: str) -> str | None:
    for sec in sections:
        if _section_layout(sec) == layout:
            return sec
    return None


def _next_section_id(sections: list[str]) -> str:
    used = {sid for sid in (_section_id(s) for s in sections) if sid}
    n = 1
    while True:
        candidate = f"section-{n:03d}"
        if candidate not in used:
            return candidate
        n += 1


def _assign_section_id(section_html: str, new_id: str) -> str:
    open_m = _SECTION_OPEN_RE.search(section_html)
    if not open_m:
        return f'<section id="{new_id}">{section_html}</section>'
    attrs = open_m.group(1) or ""
    if _ATTR_ID_RE.search(attrs):
        new_attrs = _ATTR_ID_RE.sub(f'id="{new_id}"', attrs, count=1)
    else:
        new_attrs = f' id="{new_id}"{attrs}'
    return f"<section{new_attrs}>{section_html[open_m.end() :]}"


def _set_section_title(section_html: str, title: str, layout: str) -> str:
    safe = html_lib.escape(title, quote=False)
    if layout == "section-divider":
        match = _DIVIDER_TITLE_RE.search(section_html)
        if match:
            return section_html[: match.start(1)] + safe + section_html[match.end(1) :]
    match = _H1_RE.search(section_html)
    if match:
        return section_html[: match.start(1)] + safe + section_html[match.end(1) :]
    match = _H2_RE.search(section_html)
    if match:
        return section_html[: match.start(1)] + safe + section_html[match.end(1) :]
    open_m = _SECTION_OPEN_RE.search(section_html)
    if not open_m:
        return section_html
    injection = (
        f'<div class="divider-title">{safe}</div>'
        if layout == "section-divider"
        else f"<h1>{safe}</h1>"
    )
    return section_html[: open_m.end()] + injection + section_html[open_m.end() :]


def _clone_section(
    section_html: str, *, new_id: str, title: str | None, layout: str
) -> str:
    cloned = _assign_section_id(section_html, new_id)
    if title:
        cloned = _set_section_title(cloned, title, layout)
    return cloned


def _catalog_section(layout: str, title: str, new_id: str) -> str:
    safe = html_lib.escape(title or _DEFAULT_INSERT_TITLE, quote=False)
    raw = _LAYOUT_SKELETONS[layout].format(title=safe)
    return _assign_section_id(raw, new_id)


def _section_outline_items(sections: list[str]) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for i, sec in enumerate(sections):
        meta = _section_meta(i, sec)
        items.append(
            {
                "index": i,
                "id": meta["id"],
                "title": meta["title"],
                "layout": _section_layout(sec),
            }
        )
    return items


def _mutation_payload(
    html: str, sections: list[str], section_index: int
) -> dict[str, Any]:
    return {
        "ok": True,
        "html": html,
        "section_index": section_index,
        "section_count": len(sections),
        "ids": [_section_id(s) for s in sections],
        "sections": _section_outline_items(sections),
    }


def _guard_main(original: str, new_html: str) -> dict[str, str] | None:
    if _MAIN_RE.search(original) and not _MAIN_RE.search(new_html):
        return {"error": "Refusing to write: reconstructed HTML lost <main>."}
    return None


def _insert_section_html(
    html: str,
    *,
    after_index: int = -1,
    layout: str = "content",
    title: str = "",
) -> dict[str, Any]:
    """Insert a section after ``after_index`` (-1 appends). Never returns to the model."""
    resolved_layout = _normalize_layout(layout)
    if isinstance(resolved_layout, dict):
        return resolved_layout
    prefix, sections, suffix = _split_sections(html)
    last = max(0, len(sections) - 1)
    if after_index < -1 or (sections and after_index >= len(sections)):
        return {
            "error": (
                f"after_index out of range (-1 appends, or 0..{last}; got {after_index})"
            )
        }
    insert_at = len(sections) if after_index == -1 else after_index + 1
    new_id = _next_section_id(sections)
    heading = (title or "").strip() or _DEFAULT_INSERT_TITLE
    donor = _find_layout_donor(sections, resolved_layout)
    if donor:
        new_section = _clone_section(
            donor, new_id=new_id, title=heading, layout=resolved_layout
        )
    else:
        new_section = _catalog_section(resolved_layout, heading, new_id)
    sections = [*sections[:insert_at], new_section, *sections[insert_at:]]
    new_html = _join_sections(prefix, sections, suffix)
    lost = _guard_main(html, new_html)
    if lost:
        return lost
    return _mutation_payload(new_html, sections, insert_at)


def _delete_section_html(html: str, index: int) -> dict[str, Any]:
    prefix, sections, suffix = _split_sections(html)
    if not sections:
        return {"error": "Document has no sections to delete."}
    if len(sections) <= 1:
        return {"error": "Cannot delete the last section."}
    if index < 0 or index >= len(sections):
        return {
            "error": f"index out of range (0..{len(sections) - 1}; got {index})"
        }
    del sections[index]
    new_html = _join_sections(prefix, sections, suffix)
    lost = _guard_main(html, new_html)
    if lost:
        return lost
    return _mutation_payload(new_html, sections, min(index, len(sections) - 1))


def _duplicate_section_html(html: str, index: int) -> dict[str, Any]:
    prefix, sections, suffix = _split_sections(html)
    if not sections:
        return {"error": "Document has no sections to duplicate."}
    if index < 0 or index >= len(sections):
        return {
            "error": f"index out of range (0..{len(sections) - 1}; got {index})"
        }
    layout = _section_layout(sections[index])
    clone = _clone_section(
        sections[index],
        new_id=_next_section_id(sections),
        title=None,
        layout=layout,
    )
    insert_at = index + 1
    sections = [*sections[:insert_at], clone, *sections[insert_at:]]
    new_html = _join_sections(prefix, sections, suffix)
    lost = _guard_main(html, new_html)
    if lost:
        return lost
    return _mutation_payload(new_html, sections, insert_at)


def _parse_order_arg(order: Any) -> list[int] | dict[str, str] | None:
    if order is None or order == "":
        return None
    payload = order
    if isinstance(order, str):
        try:
            payload = json.loads(order)
        except json.JSONDecodeError as exc:
            return {"error": f"order is not valid JSON: {exc}"}
    if not isinstance(payload, list) or not payload:
        return {"error": "order must be a non-empty JSON array of indexes"}
    parsed: list[int] = []
    for i, item in enumerate(payload):
        try:
            parsed.append(int(item))
        except (TypeError, ValueError):
            return {"error": f"order[{i}] must be an integer"}
    return parsed


def _reorder_sections_html(
    html: str,
    *,
    from_index: int | None = None,
    to_index: int | None = None,
    order: list[int] | None = None,
) -> dict[str, Any]:
    prefix, sections, suffix = _split_sections(html)
    if not sections:
        return {"error": "Document has no sections to reorder."}
    n = len(sections)
    if order is not None:
        if sorted(order) != list(range(n)):
            return {"error": f"order must be a permutation of 0..{n - 1}"}
        old = sections
        sections = [old[i] for i in order]
        section_index = next((i for i in range(n) if sections[i] is not old[i]), 0)
        new_html = _join_sections(prefix, sections, suffix)
        lost = _guard_main(html, new_html)
        if lost:
            return lost
        return _mutation_payload(new_html, sections, section_index)
    if from_index is None or to_index is None:
        return {"error": "Provide from_index and to_index, or order."}
    if from_index < 0 or from_index >= n or to_index < 0 or to_index >= n:
        return {
            "error": (
                f"indexes out of range (0..{n - 1}; "
                f"from={from_index}, to={to_index})"
            )
        }
    if from_index != to_index:
        item = sections.pop(from_index)
        sections.insert(to_index, item)
    new_html = _join_sections(prefix, sections, suffix)
    lost = _guard_main(html, new_html)
    if lost:
        return lost
    return _mutation_payload(new_html, sections, to_index)


def _run_section_mutation(
    slug: str,
    mutate,
    message: str,
    write_label: str,
    *,
    default_type: str = "chore",
) -> dict[str, Any]:
    """Load, mutate, persist. Strip HTML so the model never sees the document body."""
    if not agent_user_id.get():
        return {"error": "No authenticated user on this agent session."}
    resolved = _resolve_slug(slug)
    if isinstance(resolved, dict):
        return resolved
    try:
        original, _source = _load_document_text(resolved)
        if isinstance(original, dict):
            return original
        mutated = mutate(original)
        if mutated.get("error"):
            return {k: v for k, v in mutated.items() if k != "html"}
        result = _persist_document(
            resolved, str(mutated["html"]), message, default_type=default_type
        )
        if "error" not in result:
            note_documents_write(write_label)
            result["ok"] = True
            result["section_index"] = mutated["section_index"]
            result["section_count"] = mutated["section_count"]
            result["ids"] = mutated["ids"]
            leftovers = mutated.get("leftover_placeholders")
            result["leftover_placeholders"] = leftovers or []
            if mutated.get("incomplete"):
                result["incomplete"] = True
            if mutated.get("warning"):
                result["warning"] = mutated["warning"]
        result.pop("html", None)
        result.update(_open_document_note(resolved))
        return result
    except Exception as exc:  # noqa: BLE001
        return _tool_error(exc)


def _restore_redacted_data_urls(new_html: str, original_html: str) -> str:
    """If the model writes back redacted placeholders, reinstate originals in order."""
    originals = _DATA_URL_RE.findall(original_html)
    if not originals or new_html.count(_REDACTED_PLACEHOLDER) == 0:
        return new_html
    it = iter(originals)

    def _sub(_match: re.Match[str]) -> str:
        try:
            return next(it)
        except StopIteration:
            return _REDACTED_PLACEHOLDER

    return re.sub(re.escape(_REDACTED_PLACEHOLDER), _sub, new_html)


# Slide-shaped leftovers. REST and unit tests still call them. DocumentsAgent
# must not bind them once the command API is available, or a write-report turn
# lists/reads/writes leftover <section> blocks until the 160-step cap.
LEFTOVER_SECTION_TOOL_NAMES = frozenset(
    {
        "list_document_sections",
        "read_document_section",
        "write_document_section",
        "write_document_sections",
        "insert_section",
        "delete_section",
        "duplicate_section",
        "reorder_sections",
    }
)
FILL_TURN_HIDDEN_TOOL_NAMES = frozenset({"replace_in_document"})
COMMAND_TOOL_NAMES = frozenset(
    {
        "apply_document_commands",
        "insert_heading",
        "insert_paragraph",
        "insert_page_break",
        "apply_paragraph_style",
        "apply_documents_template",
        "rename_document",
        "update_title",
    }
)
_TEMPLATE_KEY_RE = re.compile(r"[^a-z0-9]+")


def _template_key(raw: str) -> str:
    return _TEMPLATE_KEY_RE.sub("-", (raw or "").strip().lower()).strip("-")


def resolve_documents_template_id(
    requested: str, catalog: list[dict[str, str]]
) -> str | dict[str, Any]:
    """Map a human name or id onto one catalog row.

    "Portrait A4" matches that name, not the blank sibling.
    """
    raw = (requested or "").strip()
    choices = [
        {"id": str(row.get("id") or ""), "name": str(row.get("name") or "")}
        for row in catalog
        if str(row.get("id") or "").strip()
    ]
    if not raw:
        return {
            "error": "template_id is required. Pass a catalog name or id.",
            "templates": choices,
        }
    stripped = re.sub(r"\b(theme|template|style|styles)\b", "", raw, flags=re.IGNORECASE)
    needle = _template_key(stripped)
    if not needle:
        return {"error": "template_id is required.", "templates": choices}

    def stem(tid: str) -> str:
        return tid.split("/", 1)[-1]

    for row in choices:
        tid = row["id"]
        if raw == tid or needle == _template_key(tid) or needle == _template_key(stem(tid)):
            return tid
    for row in choices:
        if needle == _template_key(row["name"]):
            return row["id"]

    hits = [
        row
        for row in choices
        if needle in _template_key(row["id"])
        or needle in _template_key(row["name"])
        or _template_key(stem(row["id"])).startswith(needle)
    ]
    if not hits:
        return {"error": f"Unknown template {requested!r}.", "templates": choices}
    if len(hits) == 1:
        return hits[0]["id"]
    if "blank" not in needle:
        non_blank = [row for row in hits if "blank" not in _template_key(row["id"])]
        if len(non_blank) == 1:
            return non_blank[0]["id"]
    return {"error": f"Ambiguous template {requested!r}.", "templates": hits}


def _catalog_template_rows() -> list[dict[str, str]]:
    try:
        from naas_abi.apps.nexus.apps.api.app.services.documents.adapters.primary.documents__primary_adapter__FastAPI import (
            _picker_template_records,
        )

        rows: list[dict[str, str]] = []
        for row in _picker_template_records():
            tid = str(row.get("id") or "").strip()
            if tid:
                rows.append({"id": tid, "name": str(row.get("name") or tid)})
        return rows
    except Exception:  # noqa: BLE001
        return [{"id": "article-light-v1", "name": "Article Light"}]


def _load_catalog_seed_html(template_id: str) -> str | dict[str, Any]:
    try:
        from naas_abi.apps.nexus.apps.api.app.services.documents.adapters.primary.documents__primary_adapter__FastAPI import (
            _load_seed_html,
        )

        return _load_seed_html(template_id)
    except Exception as exc:  # noqa: BLE001
        detail = getattr(exc, "detail", None)
        if isinstance(detail, str) and detail:
            return {"error": detail}
        if template_id in {"article-light-v1", "abi/article-light-v1"}:
            seed = _load_seed_document_html()
            if seed:
                return seed
        return {"error": f"Could not load template {template_id!r}: {exc}"}


def _write_project_title(slug: str, title: str) -> str | dict[str, Any]:
    """Force-update project.json display name. Slug and git folder stay put.

    The sidebar tree reads this title, not the slug. ``Untitled document`` is a
    display name. A user rename must overwrite it even when the brief looks
    like an edit instruction.
    """
    clean = (title or "").strip()
    if not clean:
        return {"error": "title is required"}
    if is_placeholder_document_title(clean):
        return {"error": "title must be a real name, not Untitled document"}
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"]}
    sc = _get_source_control()
    repo_id = _repo_id()
    meta: dict[str, Any] = {}
    try:
        existing = sc.get_file(
            repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        )
        if existing.text:
            meta = json.loads(existing.text)
    except (SourceControlError, json.JSONDecodeError, TypeError):
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    from datetime import UTC, datetime

    ws = _workspace_id()
    meta = {
        **meta,
        "slug": meta.get("slug") or slug,
        "workspace_id": str(meta.get("workspace_id") or ws or ""),
        "title": clean,
        "updated_at": datetime.now(UTC).isoformat(),
    }
    try:
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["project_path"],
            content=json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            message=f"chore(document): rename project {slug}",
            branch=paths["branch"],
            **_agent_author(),
        )
    except SourceControlError as exc:
        return {"error": _friendly_sc_error(exc)}
    documents_active_title.set(clean)
    return clean


def _stored_display_title(slug: str) -> str:
    """project.json title for the open document, or empty."""
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return ""
    try:
        existing = _get_source_control().get_file(
            repo_id=_repo_id(), path=paths["project_path"], ref=paths["branch"]
        )
        if not existing.text:
            return ""
        meta = json.loads(existing.text)
    except (SourceControlError, json.JSONDecodeError, TypeError):
        return ""
    if not isinstance(meta, dict):
        return ""
    return str(meta.get("title") or "").strip()


def maybe_auto_title_open_document(brief: str, slug: str = "") -> str | None:
    """Name a still-untitled open document from the first prompt, like Chat.

    Persists through rename_document so the sidebar display name and cover H1
    move together. A title the user already chose is never overwritten.
    """
    text = (brief or "").strip()
    if not text or text.startswith("/"):
        return None
    resolved = _resolve_slug(slug)
    if isinstance(resolved, dict):
        return None
    current = (
        _stored_display_title(resolved) or (documents_active_title.get() or "").strip()
    )
    if current and not is_placeholder_document_title(current):
        return None
    title = auto_document_title(text)
    if not title or is_placeholder_document_title(title):
        return None
    result = _rename_or_update_document(
        title,
        resolved,
        rename_project=True,
        message="feat(document): auto-title from first prompt",
    )
    if result.get("error"):
        return None
    return str(result.get("title") or title)


def _apply_rename_project(result: dict[str, Any], title: str) -> dict[str, Any]:
    """Write the sidebar display name after a successful HTML rename."""
    slug = str(result.get("slug") or "").strip()
    if not slug or not title:
        return result
    written = _write_project_title(slug, title)
    if isinstance(written, dict):
        result["project_rename_error"] = written.get("error")
        result["project_renamed"] = False
        return result
    result["title"] = written
    result["project_renamed"] = True
    result["slug_changed"] = False
    return result


def _rename_or_update_document(
    title: str,
    slug: str,
    *,
    rename_project: bool,
    message: str,
) -> dict[str, Any]:
    """Shared path for rename_document (project + HTML) and update_title (HTML)."""
    from naas_abi.agents.tools.documents_commands import update_document_title

    if not agent_user_id.get():
        return {"error": "No authenticated user on this agent session."}
    resolved = _resolve_slug(slug)
    if isinstance(resolved, dict):
        return resolved
    clean = (title or "").strip()
    if not clean:
        return {"error": "title is required"}
    if rename_project and is_placeholder_document_title(clean):
        return {"error": "title must be a real name, not Untitled document"}
    try:
        html, source = _load_document_text(resolved)
        if isinstance(html, dict):
            return html
        cover_before = _cover_h1_text(html)
        updated = update_document_title(html, clean)
        if isinstance(updated, dict):
            return updated
        result: dict[str, Any]
        if updated != html:
            result = _persist_document(resolved, updated, message, default_type="feat")
            if "error" in result:
                return result
        else:
            result = {
                "ok": True,
                "slug": resolved,
                "source": source,
                "title": clean,
            }
        cover_after = _cover_h1_text(updated)
        result["ok"] = True
        result["slug"] = resolved
        result["cover_h1_before"] = cover_before
        result["cover_h1_after"] = cover_after
        result["cover_h1_updated"] = bool(
            cover_before is not None
            and cover_after is not None
            and cover_before != cover_after
        )
        result["slug_changed"] = False
        if rename_project:
            result = _apply_rename_project(result, clean)
        else:
            result["title"] = clean
            result["project_renamed"] = False
        note_documents_write("rename document" if rename_project else "document title")
        result.update(_open_document_note(resolved))
        return result
    except Exception as exc:  # noqa: BLE001
        return _tool_error(exc)


def _write_project_template_id(slug: str, template_id: str) -> None:
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return
    sc = _get_source_control()
    repo_id = _repo_id()
    meta: dict[str, Any] = {}
    try:
        existing = sc.get_file(
            repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        )
        if existing.text:
            meta = json.loads(existing.text)
    except Exception:  # noqa: BLE001
        meta = {}
    if not isinstance(meta, dict):
        meta = {}
    meta["template_id"] = template_id
    meta["slug"] = meta.get("slug") or slug
    try:
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["project_path"],
            content=json.dumps(meta, indent=2, ensure_ascii=False) + "\n",
            message=f"chore(sections): apply template {template_id}",
            branch=paths["branch"],
            **_agent_author(),
        )
    except SourceControlError:
        return


def _view_for_llm(html: str) -> dict[str, Any]:
    """Outline-only document view. Full HTML belongs in one targeted section read."""
    from naas_abi.agents.tools.documents_commands import (
        leftover_placeholders,
        leftover_slots,
    )

    scripts_redacted_html, n_scripts = _redact_scripts(html)
    redacted, n_assets = _redact_data_urls(scripts_redacted_html)
    _prefix, sections, _suffix = _split_sections(html)
    leftovers = leftover_placeholders(html)
    slots = leftover_slots(html)
    return {
        "chars": len(html),
        "chars_redacted": len(redacted),
        "section_count": len(sections),
        "sections": [_section_meta(i, sec) for i, sec in enumerate(sections)],
        "redacted_scripts": n_scripts,
        "redacted_assets": n_assets,
        "leftover_placeholders": leftovers,
        "leftover_slots": slots,
        "note": (
            "Outline only. HTML is omitted on purpose: a 25-section industry "
            "document is ~160k characters and blows the next model call. "
            "Fill the open template with one apply_document_commands. "
            "leftover_slots is the required batch: copy every find and "
            "class_name. Each replace must be a full topic sentence. "
            "leftover_slots is empty only when those slots have real prose. "
            "Do not write the memo only in chat. "
            "Do not leave seed placeholder copy. Do not append after the footer. "
            "Do not edit buildPptx. Preview is HTML; PDF is derived at export."
        ),
    }


def documents_tools() -> list[BaseTool]:
    @tool
    def create_documents_project(title: str) -> dict[str, Any]:
        """Create a new Documents document and make it the document you are editing.

        Use this when the user asks for a document, document, or sections and no
        document is open yet (for example from the main chat surface). It seeds the
        Minimal Light template, then every later sections tool acts on this document
        without needing a slug.

        Pass a short human title for the topic, in the user's language. Passing
        the raw request is tolerated: the topic is extracted from it.

        After creating it, research the topic with web_search and then write the
        documents. Do not ask the user which document to edit.

        If a document is already open, this returns that slug and creates nothing.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        open_slug = (documents_active_slug.get() or "").strip()
        if open_slug:
            return {
                "ok": True,
                "created": False,
                "slug": open_slug,
                "title": (documents_active_title.get() or "").strip(),
                **_open_document_note(open_slug),
                "note": (
                    "A document is already open. Do not create another. "
                    "Fill the open template with one apply_document_commands batch. "
                    "Replace each entire seed slot. Do not append leftover instructional tails."
                ),
            }
        # The document name shows up in the sidebar tree, the chat card, and the
        # URL, so never keep template filler or a whole sentence.
        clean_title = resolve_document_title(title, documents_brief.get() or "")
        base = _slugify_title(clean_title)
        if not base:
            return {"error": "title must contain letters or digits"}
        try:
            sc = _get_source_control()
            repo_id = _ensure_coding_repo()
            taken = {b.name for b in sc.list_branches(repo_id=repo_id)}
            slug = _unique_slug(base, taken)

            # _ensure_project_json reads the title from context.
            documents_active_title.set(clean_title)
            paths = _ensure_sections_write_paths(slug)
            if paths.get("error"):
                return {"error": paths["error"]}

            seed = _load_seed_document_html()
            if not seed:
                return {"error": "Documents template is missing; cannot seed a document."}
            commit = sc.upsert_file(
                repo_id=repo_id,
                path=paths["document_path"],
                content=_seed_document_with_title(seed, clean_title),
                message=f"feat(sections): create {slug}",
                branch=paths["branch"],
                **_agent_author(),
            )

            # Become the active document for the rest of this conversation.
            documents_active_slug.set(slug)
            _remember_active_slug(slug)
            return {
                "ok": True,
                "created": True,
                "slug": slug,
                "title": clean_title,
                "branch": paths["branch"],
                "path": paths["document_path"],
                "workspace_id": _workspace_id() or "",
                "template_id": "article-light-v1",
                "commit_sha": commit.sha,
                "note": (
                    f"Created '{clean_title}'. This is now the open document. "
                    "Research the topic with web_search, then fill the open "
                    "template. Do not leave seed placeholder copy. "
                    "Do not append after the footer."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def list_documents_projects() -> dict[str, Any]:
        """List Documents projects in the workspace monorepo (branches documents/<slug>).

        When a document is already open in the Documents UI, prefer that open slug from
        context instead of asking the user which document to edit.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        open_slug = documents_active_slug.get()
        try:
            sc = _get_source_control()
            repo_id = _ensure_coding_repo()
            ws = _workspace_id()
            ws_seg = _workspace_segment(ws) if ws else None
            ns_prefix = f"{_BRANCH_PREFIX}{ws_seg}/" if ws_seg else None
            projects = []
            for branch in sc.list_branches(repo_id=repo_id):
                name = branch.name
                slug = ""
                if ns_prefix and name.startswith(ns_prefix):
                    slug = name[len(ns_prefix) :]
                elif name.startswith(_BRANCH_PREFIX) and "/" not in name[len(_BRANCH_PREFIX) :]:
                    slug = name[len(_BRANCH_PREFIX) :]
                else:
                    continue
                if not _SLUG_RE.match(slug):
                    continue
                title = slug.replace("-", " ").title()
                project_path = (
                    _project_path(slug, ws)
                    if ns_prefix and name.startswith(ns_prefix)
                    else _legacy_project_path(slug)
                )
                try:
                    meta = sc.get_file(
                        repo_id=repo_id, path=project_path, ref=branch.name
                    )
                    data = json.loads(meta.text) if meta.text else {}
                    title = str(data.get("title") or title)
                    owner = str(data.get("workspace_id") or "").strip()
                    if ws and owner and owner != ws:
                        continue
                    if (
                        ws
                        and "/" not in name[len(_BRANCH_PREFIX) :]
                        and not owner
                    ):
                        # Unscoped legacy: hide until claimed via Documents UI.
                        continue
                except (SourceControlError, json.JSONDecodeError):
                    if ws and "/" not in name[len(_BRANCH_PREFIX) :]:
                        continue
                projects.append(
                    {
                        "slug": slug,
                        "title": title,
                        "branch": branch.name,
                        "document_path": (
                            _document_path(slug, ws)
                            if ns_prefix and name.startswith(ns_prefix)
                            else _legacy_document_path(slug)
                        ),
                        "is_open": bool(open_slug and open_slug == slug),
                    }
                )
            out: dict[str, Any] = {"projects": projects}
            if open_slug:
                matched = [row for row in projects if row["slug"] == open_slug]
                if matched:
                    out["projects"] = matched
                out["open_slug"] = open_slug
                out["note"] = (
                    f"The user already has '{open_slug}' open. "
                    "Edit that document. For a theme or template, call "
                    "apply_documents_template. Do not list or read other documents."
                )
            return out
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def list_document_sections(slug: str = "") -> dict[str, Any]:
        """List ``<section>`` sections in a document (index, id, title). Call once per turn.

        Omit slug when a document is open in the Documents UI; the open document is used.
        Do not list again before each write. After this, write the document.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        blocked = reject_repeat_list_document_sections()
        if blocked:
            return blocked
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            html, source = _load_document_text(resolved)
            if isinstance(html, dict):
                return html
            _prefix, sections, _suffix = _split_sections(html)
            note_documents_list()
            return {
                **_open_document_note(resolved),
                "slug": resolved,
                "path": _document_path(resolved),
                "source": source,
                "section_count": len(sections),
                "chars": len(html),
                "sections": [_section_meta(i, sec) for i, sec in enumerate(sections)],
            }
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def read_document_section(
        slug: str = "",
        index: int | None = None,
        section_id: str | None = None,
    ) -> dict[str, Any]:
        """Read one section ``<section>`` by index or id. Embedded data-URLs are redacted.

        Omit slug when a document is open in the Documents UI.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            html, source = _load_document_text(resolved)
            if isinstance(html, dict):
                return html
            _prefix, sections, _suffix = _split_sections(html)
            resolved_idx = _resolve_section_index(sections, index, section_id)
            if isinstance(resolved_idx, dict):
                return resolved_idx
            blocked = reject_documents_section_read(resolved_idx)
            if blocked:
                return blocked
            note_documents_section_read(resolved_idx)
            section_html = sections[resolved_idx]
            redacted, n_assets = _redact_data_urls(section_html)
            meta = _section_meta(resolved_idx, section_html)
            return {
                **_open_document_note(resolved),
                "slug": resolved,
                "path": _document_path(resolved),
                "source": source,
                **meta,
                "html": redacted,
                "note": (
                    f"Redacted {n_assets} embedded data-URL asset(s). "
                    "Do not re-read this section after you write it. "
                    "For a full-document rewrite, use write_document_sections instead of "
                    "reading every section."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def write_document_section(
        html: str,
        slug: str = "",
        index: int | None = None,
        section_id: str | None = None,
        message: str = "refactor(sections): rewrite section via Abi",
    ) -> dict[str, Any]:
        """Replace one section. For a full-document rewrite, use write_document_sections.

        Omit slug when a document is open. Pass the full ``<section>...</section>``
        for that section. If html still contains ``[REDACTED_DATA_URL]`` placeholders
        from a prior read, original embedded assets are restored automatically.

        For news, current events, or factual briefs: call web_search once this
        turn first. Later writes in the same turn do not need another search.
        """
        blocked = reject_unresearched_documents_write()
        if blocked:
            return blocked
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        if not html or not html.strip():
            return {"error": "html must be a non-empty string"}
        if "<section" not in html.lower():
            return {"error": "html must include a <section>...</section> block"}
        try:
            original, _source = _load_document_text(resolved)
            if isinstance(original, dict):
                return original
            applied = _apply_section_writes(
                original, [{"html": html, "index": index, "section_id": section_id}]
            )
            if isinstance(applied, dict):
                return applied
            new_html, written = applied
            result = _persist_document(
                resolved,
                new_html,
                message or "refactor(sections): rewrite section via Abi",
                default_type="refactor",
            )
            if "error" not in result and written:
                result["section_index"] = written[0]
                note_documents_write(f"section {written[0] + 1}")
            result.update(_open_document_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def write_document_sections(
        sections: str,
        slug: str = "",
        message: str = "refactor(sections): rewrite sections via Abi",
    ) -> dict[str, Any]:
        """Replace several sections in one persist. Use this for a full-document rewrite.

        ``sections`` is a JSON array of objects:
        ``[{"index": 0, "html": "<section>...</section>"}, ...]``
        ``section_id`` may replace ``index``. One persist for the whole batch.
        Do not list or re-read after this call.

        For news or factual briefs: call web_search once this turn first.
        Later writes in the same turn do not need another search.
        """
        blocked = reject_unresearched_documents_write()
        if blocked:
            return blocked
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        parsed = _parse_section_writes(sections)
        if isinstance(parsed, dict) and "error" in parsed:
            return parsed
        try:
            original, _source = _load_document_text(resolved)
            if isinstance(original, dict):
                return original
            applied = _apply_section_writes(original, parsed)
            if isinstance(applied, dict):
                return applied
            new_html, written = applied
            result = _persist_document(
                resolved,
                new_html,
                message or "refactor(sections): rewrite sections via Abi",
                default_type="refactor",
            )
            if "error" not in result and written:
                labels = [f"section {idx + 1}" for idx in written]
                note_documents_write(", ".join(labels))
                result["section_indexes"] = written
                result["sections_written"] = len(written)
            result.update(_open_document_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def replace_in_document(
        old: str,
        new: str,
        slug: str = "",
        occurrence: int = 0,
        section_index: int | None = None,
        section_id: str | None = None,
        message: str = "fix(sections): replace text via Abi",
    ) -> dict[str, Any]:
        """Surgically replace a string in the open document without dumping full HTML in chat.

        Omit slug when a document is open in the Documents UI. occurrence: 0 replaces all
        matches; 1 replaces the first, 2 the second, etc. Matches HTML entities
        flexibly (``&``/``&amp;``, ``—``/``&mdash;``/``&#8212;``, ``–``/``&ndash;``)
        so cover ``<h1>`` / subtitle HTML updates. PDF export reads that live
        DOM; do not edit ``buildPptx`` or ``FOOTER_TXT``.

        For cover / title / \"section 1\" edits: pass section_index=0 (or
        section_id of the cover) and occurrence=0. Do not use occurrence=1 for
        \"the title\": document order hits ``<title>`` / menubar before the cover
        ``<h1>`` that Preview shows. Confirm ``cover_h1_updated`` /
        ``cover_subtitle_updated`` in the tool result before claiming Preview
        and PDF changed.

        For news, current events, or factual briefs: call web_search once this
        turn first. Later writes in the same turn do not need another search.
        """
        fill_blocked = reject_replace_in_document_on_fill()
        if fill_blocked:
            return fill_blocked
        blocked = reject_unresearched_documents_write()
        if blocked:
            return blocked
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        if not old:
            return {"error": "old must be a non-empty string"}
        try:
            html, source = _load_document_text(resolved)
            if isinstance(html, dict):
                return html
            cover_before = _cover_h1_text(html)
            subtitle_before = _cover_subtitle_text(html)
            applied = _apply_replacements_in_section(
                html,
                old,
                new,
                occurrence,
                section_index=section_index,
                section_id=section_id,
            )
            if isinstance(applied, dict):
                applied["source"] = source
                applied["cover_h1_before"] = cover_before
                applied["cover_subtitle_before"] = subtitle_before
                return applied
            updated, count, replaced, resolved_section = applied
            result = _persist_document(
                resolved,
                updated,
                message or "fix(sections): replace text via Abi",
                default_type="fix",
            )
            if "error" not in result:
                label = (
                    f"section {resolved_section + 1} text"
                    if resolved_section >= 0
                    else "document text"
                )
                note_documents_write(label)
            cover_after = _cover_h1_text(updated)
            subtitle_after = _cover_subtitle_text(updated)
            result["matches_found"] = count
            result["replacements"] = replaced
            result["read_source"] = source
            result["cover_h1_before"] = cover_before
            result["cover_h1_after"] = cover_after
            result["cover_h1_updated"] = bool(
                cover_before is not None
                and cover_after is not None
                and cover_before != cover_after
            )
            result["cover_subtitle_before"] = subtitle_before
            result["cover_subtitle_after"] = subtitle_after
            result["cover_subtitle_updated"] = bool(
                subtitle_before is not None
                and subtitle_after is not None
                and subtitle_before != subtitle_after
            )
            if resolved_section >= 0:
                result["section_index"] = resolved_section
            old_plain = html_lib.unescape(old)
            warnings: list[str] = []
            if (
                cover_before
                and old_plain in html_lib.unescape(cover_before)
                and not result["cover_h1_updated"]
            ):
                warnings.append(
                    "Cover <h1> still contains the old title. Retry with "
                    "section_index=0 and occurrence=0 so Preview updates."
                )
            if (
                subtitle_before
                and old_plain in html_lib.unescape(subtitle_before)
                and not result["cover_subtitle_updated"]
            ):
                warnings.append(
                    "Cover subtitle still contains the old text. Retry with "
                    "section_index=0 and occurrence=0 so Preview updates."
                )
            if warnings:
                result["warning"] = " ".join(warnings)
            result.update(_open_document_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def read_document(slug: str = "", include_assets: bool = False) -> dict[str, Any]:
        """Read a compact outline of the HTML document (titles, counts, no HTML).

        Omit slug when a document is open. Default omits the file body: a 25-section
        industry document is ~160k characters. Prefer apply_document_commands,
        then stop. Set include_assets=true only if you must see scripts or
        embedded images (that path can exceed the model context window).
        """
        blocked = reject_read_document()
        if blocked:
            return blocked
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            html, source = _load_document_text(resolved)
            if isinstance(html, dict):
                return html
            if include_assets:
                note_documents_list()
                return {
                    **_open_document_note(resolved),
                    "slug": resolved,
                    "path": _document_path(resolved),
                    "source": source,
                    "html": html,
                    "chars": len(html),
                    "warning": (
                        "Full document with scripts/assets. This can exceed model "
                        "context limits. Prefer section tools for edits."
                    ),
                }
            view = _view_for_llm(html)
            note_documents_list()
            return {
                **_open_document_note(resolved),
                "slug": resolved,
                "path": _document_path(resolved),
                "source": source,
                **view,
            }
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def write_document(
        html: str,
        slug: str = "",
        message: str = "refactor(sections): rewrite document via Abi",
    ) -> dict[str, Any]:
        """Write the full HTML document. Prefer apply_document_commands for a report.

        Omit slug when a document is open. Do not follow with leftover section writes.
        For a single copy edit, use replace_in_document instead.

        For news, current events, or factual briefs: call web_search once this
        turn first. Later writes in the same turn do not need another search.
        """
        blocked = reject_unresearched_documents_write()
        if blocked:
            return blocked
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        if not html or not html.strip():
            return {"error": "html must be a non-empty string"}
        if _SCRIPT_PLACEHOLDER in html:
            return {
                "error": (
                    "html contains REDACTED_SCRIPT placeholders; refusing to "
                    "overwrite document scripts. Use replace_in_document or "
                    "write_document_section instead."
                )
            }
        try:
            original = ""
            try:
                loaded, _source = _load_document_text(resolved)
                if isinstance(loaded, str):
                    original = loaded
            except Exception:  # noqa: BLE001
                original = ""
            content = (
                _restore_redacted_data_urls(html, original) if original else html
            )
            result = _persist_document(
                resolved,
                content,
                message or "refactor(sections): rewrite document via Abi",
                default_type="refactor",
            )
            if "error" not in result:
                note_documents_write("full document")
            result.update(_open_document_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    def _run_document_commands(requests: list[dict[str, Any]], slug: str, message: str) -> dict[str, Any]:
        blocked = reject_unresearched_documents_write()
        if blocked:
            return blocked
        from naas_abi.agents.tools.documents_commands import (
            apply_document_commands as apply_commands,
        )
        from naas_abi.agents.tools.documents_commands import (
            last_rename_document_title,
        )

        result = _run_section_mutation(
            slug,
            lambda html: apply_commands(html, requests),
            message,
            "document commands",
            default_type="feat",
        )
        if "error" not in result:
            result["heading_index"] = result.get("section_index")
            result["heading_count"] = result.get("section_count")
            rename_title = last_rename_document_title(requests)
            if rename_title:
                result = _apply_rename_project(result, rename_title)
        return result

    @tool
    def apply_document_commands(
        requests_json: str,
        slug: str = "",
        message: str = "feat(document): apply commands via Abi",
    ) -> dict[str, Any]:
        """Apply an ordered list of document commands (JSON array).

        Fill the open template in this one batch. leftover_slots is the
        required batch: every find and class_name, each with a non-empty
        topic-sentence replace. leftover_slots is empty only when those
        slots have real prose. Do not write the memo only in chat.
        A leftover phrase replaces that whole seed block. replace_class
        on palette, fm-table, fm-shaded, intro, subtitle, note. Insert a
        heading only when the brief needs a section the seed does not have.
        Writes land inside .doc-body. Do not append after the footer.
        If leftover_placeholders is not empty after this call, stop.
        Do not apply again this turn.

        Each item needs type. Supported: insert_text, insert_paragraph,
        insert_heading, insert_page_break, delete_range, replace_text,
        replace_class, update_paragraph_style, update_title, rename_document.
        Positions use after_heading or heading_index. rename_document also
        updates the sidebar display name. Returns
        {ok, heading_index, heading_count, leftover_placeholders}. Never HTML.

        For news or factual briefs: call web_search once this turn first.
        """
        repeat = reject_repeat_apply_document_commands()
        if repeat:
            return repeat
        try:
            payload = json.loads(requests_json or "[]")
        except json.JSONDecodeError as exc:
            return {"error": f"requests_json is not valid JSON: {exc}"}
        if not isinstance(payload, list):
            return {"error": "requests_json must be a JSON array"}
        result = _run_document_commands(
            payload, slug, message or "feat(document): apply commands via Abi"
        )
        if "error" not in result:
            result["heading_index"] = result.get("section_index")
            result["heading_count"] = result.get("section_count")
        return result

    @tool
    def insert_page_break(
        after_heading: int = -1,
        slug: str = "",
        message: str = "feat(document): insert page break via Abi",
    ) -> dict[str, Any]:
        """Insert a hard page break after after_heading (-1 = last heading).

        Same primitive as Google Docs insertPageBreak and ODF fo:break-before=page.
        Not a new section and not a slide.
        """
        return _run_document_commands(
            [{"type": "insert_page_break", "after_heading": after_heading}],
            slug,
            message or "feat(document): insert page break via Abi",
        )

    @tool
    def insert_heading(
        title: str = "Heading",
        level: int = 2,
        after_heading: int = -1,
        slug: str = "",
        message: str = "feat(document): insert heading via Abi",
    ) -> dict[str, Any]:
        """Insert a heading (level 1-3) after after_heading, inside .doc-body.

        Prefer replace_text on seed headings. Insert only when the brief needs
        a section the seed does not have. Do not append after the footer.
        """
        return _run_document_commands(
            [
                {
                    "type": "insert_heading",
                    "title": title,
                    "level": level,
                    "after_heading": after_heading,
                }
            ],
            slug,
            message or "feat(document): insert heading via Abi",
        )

    @tool
    def insert_paragraph(
        text: str = "",
        after_heading: int = -1,
        slug: str = "",
        message: str = "feat(document): insert paragraph via Abi",
    ) -> dict[str, Any]:
        """Insert a paragraph after after_heading, inside .doc-body.

        Prefer replace_text on seed copy. Do not append after the footer.
        """
        return _run_document_commands(
            [{"type": "insert_paragraph", "text": text, "after_heading": after_heading}],
            slug,
            message or "feat(document): insert paragraph via Abi",
        )

    @tool
    def rename_document(
        title: str,
        slug: str = "",
        message: str = "feat(document): rename document via Abi",
    ) -> dict[str, Any]:
        """Rename the open document: sidebar folder and visible title together.

        Use this when the user says "rename this doc" or "rename this document".
        Updates project.json display name and the HTML tab plus cover H1 to the
        same name. The slug and git folder stay put.

        For a heading-only change ("change the title", "change the heading"),
        use update_title instead.
        """
        return _rename_or_update_document(
            title,
            slug,
            rename_project=True,
            message=message or "feat(document): rename document via Abi",
        )

    @tool
    def update_title(
        title: str,
        slug: str = "",
        message: str = "feat(document): update title via Abi",
    ) -> dict[str, Any]:
        """Change the visible document title (tab + cover H1) only.

        Use this when the user says "change the title" or "change the heading".
        Does not rename the sidebar folder. Use rename_document when they say
        "rename this doc".
        """
        return _rename_or_update_document(
            title,
            slug,
            rename_project=False,
            message=message or "feat(document): update title via Abi",
        )

    @tool
    def apply_paragraph_style(
        heading_index: int,
        style: str,
        slug: str = "",
        message: str = "style(document): apply paragraph style via Abi",
    ) -> dict[str, Any]:
        """Retag a heading: heading1, heading2, heading3, or paragraph.

        Google Docs updateParagraphStyle analog.
        """
        return _run_document_commands(
            [
                {
                    "type": "update_paragraph_style",
                    "heading_index": heading_index,
                    "style": style,
                }
            ],
            slug,
            message or "style(document): apply paragraph style via Abi",
        )

    @tool
    def insert_section(
        after_index: int = -1,
        layout: str = "content",
        title: str = "",
        slug: str = "",
        message: str = "feat(sections): insert section via Abi",
    ) -> dict[str, Any]:
        """Leftover slide-shaped insert of a <section> block.

        Prefer insert_heading, insert_paragraph, insert_page_break, or
        apply_document_commands. layout cover / section-divider / content
        clones a skeleton. page-break is accepted but insert_page_break is
        the document verb. Returns {ok, section_index, section_count, ids}.
        Never HTML.
        """
        return _run_section_mutation(
            slug,
            lambda html: _insert_section_html(
                html, after_index=after_index, layout=layout, title=title
            ),
            message or "feat(sections): insert section via Abi",
            "insert section",
            default_type="feat",
        )

    @tool
    def delete_section(
        index: int,
        slug: str = "",
        message: str = "refactor(sections): delete section via Abi",
    ) -> dict[str, Any]:
        """Delete the section at index. Refuses when it is the last section.

        Returns {ok, section_index, section_count, ids}. Never HTML.
        """
        return _run_section_mutation(
            slug,
            lambda html: _delete_section_html(html, index),
            message or "refactor(sections): delete section via Abi",
            f"delete section {index + 1}",
            default_type="refactor",
        )

    @tool
    def duplicate_section(
        index: int,
        slug: str = "",
        message: str = "feat(sections): duplicate section via Abi",
    ) -> dict[str, Any]:
        """Duplicate the section at index and insert the copy after it.

        Returns {ok, section_index, section_count, ids}. Never HTML.
        """
        return _run_section_mutation(
            slug,
            lambda html: _duplicate_section_html(html, index),
            message or "feat(sections): duplicate section via Abi",
            f"duplicate section {index + 1}",
            default_type="feat",
        )

    @tool
    def reorder_sections(
        from_index: int = 0,
        to_index: int = 0,
        order: str = "",
        slug: str = "",
        message: str = "style(sections): reorder sections via Abi",
    ) -> dict[str, Any]:
        """Move a section from from_index to to_index, or pass order as a JSON index list.

        Returns {ok, section_index, section_count, ids}. Never HTML.
        """
        parsed = _parse_order_arg(order)
        if isinstance(parsed, dict):
            return parsed

        def _mutate(html: str) -> dict[str, Any]:
            if parsed is not None:
                return _reorder_sections_html(html, order=parsed)
            return _reorder_sections_html(
                html, from_index=from_index, to_index=to_index
            )

        return _run_section_mutation(
            slug,
            _mutate,
            message or "style(sections): reorder sections via Abi",
            "reorder sections",
            default_type="style",
        )

    @tool
    def apply_documents_template(template_id: str = "", slug: str = "") -> dict[str, Any]:
        """Apply a catalog seed (Portrait A4, Landscape A4, ...) to the open document.

        Use this when the user asks for a theme or template. Do not list other
        documents and do not read_file their HTML. Replaces document.html with
        the seed. Then fill every seed slot with apply_document_commands.
        Do not leave placeholder copy. Do not append after the footer.
        Theme changes skip the research gate.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        catalog = _catalog_template_rows()
        resolved = resolve_documents_template_id(template_id, catalog)
        if isinstance(resolved, dict):
            return resolved
        target = _resolve_slug(slug)
        if isinstance(target, dict):
            return target
        seed = _load_catalog_seed_html(resolved)
        if isinstance(seed, dict):
            return seed
        if not seed.strip():
            return {"error": f"Template {resolved!r} is empty."}
        try:
            paths = _ensure_sections_write_paths(target)
            if paths.get("error"):
                return {"error": paths["error"]}
            result = _persist_document(
                target,
                seed,
                f"feat(sections): apply template {resolved}",
                default_type="feat",
            )
            if result.get("error"):
                return result
            _write_project_template_id(target, resolved)
            note_documents_write(f"template {resolved}")
            return {
                **_open_document_note(target),
                **result,
                "ok": True,
                "template_id": resolved,
                "wiped": True,
                "note": (
                    f"Applied {resolved}. document.html is the seed. "
                    "Fill the open template. Do not leave seed placeholder "
                    "copy. Do not append after the footer."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

    @tool
    def sections_history(slug: str = "", limit: int = 10) -> dict[str, Any]:
        """List recent commits on a Documents project branch (Forgejo version history)."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            sc = _get_source_control()
            commits = sc.list_commits(
                repo_id=_repo_id(),
                ref=_branch(resolved),
                limit=max(1, min(int(limit or 10), 50)),
            )
            return {
                **_open_document_note(resolved),
                "slug": resolved,
                "source": "forgejo",
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
            return _tool_error(exc)

    return [
        create_documents_project,
        list_documents_projects,
        list_document_sections,
        read_document_section,
        write_document_section,
        write_document_sections,
        replace_in_document,
        read_document,
        write_document,
        apply_document_commands,
        apply_documents_template,
        rename_document,
        update_title,
        insert_heading,
        insert_paragraph,
        insert_page_break,
        apply_paragraph_style,
        insert_section,
        delete_section,
        duplicate_section,
        reorder_sections,
        sections_history,
    ]


def documents_agent_tools() -> list[BaseTool]:
    """Tools DocumentsAgent binds.

    Leftover slide-shaped section CRUD is omitted when the command API is
    present, so a write-report turn cannot list/read/write leftover sections
    until the step cap.
    """
    tools = documents_tools()
    names = {tool.name for tool in tools}
    if "apply_document_commands" in names:
        hidden = LEFTOVER_SECTION_TOOL_NAMES | FILL_TURN_HIDDEN_TOOL_NAMES
        return [tool for tool in tools if tool.name not in hidden]
    return tools
