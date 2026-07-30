"""Abi tools for Nexus Slides projects.

Prefer the Coder workspace sidecar filesystem when a slides runtime is bound
to the request (Continue-parity). Fall back to Forgejo with an explicit note.

Decks live at ``slides/<slug>/deck.html`` on branch ``slides/<slug>``. When the
user has a deck open in Nexus, ``slides_active_slug`` is set so tools default
to that deck and Abi must not ask which presentation to edit.

Template decks keep slide markup in ``<main>`` (~tens of KB) but also ship
inline PPTX/asset ``<script>`` blobs (~1MB with base64 images). Tools therefore:

- expose section-scoped read/write and surgical string replace
- redact heavy scripts / data-URLs on full-deck reads
"""

from __future__ import annotations

import json
import re
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi_core.services.agent.context import (
    agent_user_id,
    coder_workspace_base,
    slides_active_mode,
    slides_active_slug,
    slides_active_title,
)
from naas_abi_core.services.agent.tools.workspace_tools import _call as _sidecar_call
from naas_abi_core.services.source_control.SourceControlPorts import SourceControlError

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
_BRANCH_PREFIX = "slides/"
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
_TAG_RE = re.compile(r"<[^>]+>")
_REDACTED_PLACEHOLDER = "[REDACTED_DATA_URL]"
_SCRIPT_PLACEHOLDER = "<!-- REDACTED_SCRIPT -->"


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


def _resolve_slug(slug: str | None) -> str | dict[str, Any]:
    """Prefer explicit slug; else the open deck from pane context."""
    candidate = (slug or "").strip() or (slides_active_slug.get() or "").strip()
    if not candidate:
        return {
            "error": (
                "No slides deck in context. Open a presentation in Slides, "
                "or pass slug explicitly."
            )
        }
    if not _SLUG_RE.match(candidate):
        return {"error": "Invalid slug (lowercase kebab-case required)."}
    return candidate


def _open_deck_note(slug: str) -> dict[str, Any]:
    title = slides_active_title.get()
    mode = slides_active_mode.get()
    note: dict[str, Any] = {
        "open_deck": {
            "slug": slug,
            "path": _deck_path(slug),
            "branch": _branch(slug),
        }
    }
    if title:
        note["open_deck"]["title"] = title
    if mode:
        note["open_deck"]["mode"] = mode
    return note


def _sidecar_available() -> bool:
    return bool(coder_workspace_base.get())


def _load_deck_via_sidecar(slug: str) -> str | dict[str, Any]:
    result = _sidecar_call("read_file", {"path": _deck_path(slug)})
    if result.get("error"):
        return {"error": result["error"], "source": "sidecar"}
    if result.get("binary"):
        return {"error": "Deck is not UTF-8 text", "source": "sidecar"}
    content = result.get("content")
    if not isinstance(content, str):
        return {"error": "Sidecar read returned no content", "source": "sidecar"}
    return content


def _write_deck_via_sidecar(slug: str, html: str) -> dict[str, Any]:
    result = _sidecar_call(
        "write_file", {"path": _deck_path(slug), "content": html}
    )
    if result.get("error") or result.get("ok") is False:
        return {
            "error": result.get("error") or "sidecar write failed",
            "source": "sidecar",
        }
    return {
        "ok": True,
        "slug": slug,
        "path": _deck_path(slug),
        "source": "sidecar",
        "bytes": result.get("bytes"),
    }


def _load_deck_via_forgejo(slug: str) -> str | dict[str, Any]:
    sc = _get_source_control()
    file = sc.get_file(repo_id=_repo_id(), path=_deck_path(slug), ref=_branch(slug))
    if file.is_binary or file.text is None:
        return {"error": "Deck is not UTF-8 text", "source": "forgejo"}
    return file.text


def _commit_deck_forgejo(slug: str, html: str, message: str) -> dict[str, Any]:
    sc = _get_source_control()
    commit = sc.upsert_file(
        repo_id=_repo_id(),
        path=_deck_path(slug),
        content=html,
        message=message,
        branch=_branch(slug),
    )
    return {
        "slug": slug,
        "path": _deck_path(slug),
        "commit_sha": commit.sha,
        "message": commit.message,
        "source": "forgejo",
    }


def _load_deck_text(slug: str) -> tuple[str | dict[str, Any], str]:
    """Load deck HTML. Returns (html_or_error, source). Prefer sidecar."""
    if _sidecar_available():
        loaded = _load_deck_via_sidecar(slug)
        if isinstance(loaded, str):
            return loaded, "sidecar"
        # Fall through to Forgejo when sidecar is bound but read failed.
        forgejo = _load_deck_via_forgejo(slug)
        if isinstance(forgejo, str):
            return forgejo, "forgejo-fallback"
        return loaded, "sidecar"
    forgejo = _load_deck_via_forgejo(slug)
    if isinstance(forgejo, str):
        return forgejo, "forgejo"
    return forgejo, "forgejo"


def _persist_deck(slug: str, html: str, message: str) -> dict[str, Any]:
    """Write editing context (sidecar) then version storage (Forgejo)."""
    sources: list[str] = []
    sidecar_result: dict[str, Any] | None = None
    if _sidecar_available():
        sidecar_result = _write_deck_via_sidecar(slug, html)
        if sidecar_result.get("ok"):
            sources.append("sidecar")
        else:
            # Keep going: Forgejo write still updates the Nexus UI deck.
            sources.append("sidecar-failed")
    try:
        forgejo = _commit_deck_forgejo(slug, html, message)
        sources.append("forgejo")
        result = {**forgejo, "sources": sources}
        if sidecar_result and not sidecar_result.get("ok"):
            result["sidecar_error"] = sidecar_result.get("error")
            result["note"] = (
                "Wrote Forgejo only; Coder sidecar write failed. "
                "Runtime may still be starting."
            )
        elif "sidecar" in sources:
            result["note"] = (
                "Updated Coder workspace files and committed to Forgejo."
            )
        return result
    except Exception as exc:  # noqa: BLE001
        if sidecar_result and sidecar_result.get("ok"):
            return {
                **sidecar_result,
                "sources": sources,
                "forgejo_error": str(exc),
                "note": (
                    "Updated Coder workspace files; Forgejo commit failed. "
                    "Use File → Save later, or retry."
                ),
            }
        return {"error": str(exc), "sources": sources}


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
    """Split deck HTML into prefix, ``<section>`` blocks (inside main), suffix.

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


def _view_for_llm(html: str) -> dict[str, Any]:
    """Compact deck view safe to place in model context."""
    scripts_redacted_html, n_scripts = _redact_scripts(html)
    redacted, n_assets = _redact_data_urls(scripts_redacted_html)
    prefix, sections, _suffix = _split_sections(html)
    return {
        "html": redacted,
        "chars": len(html),
        "chars_redacted": len(redacted),
        "section_count": len(sections),
        "redacted_scripts": n_scripts,
        "redacted_assets": n_assets,
        "note": (
            "Heavy <script> blocks (PPTX/assets) and data-URLs are redacted. "
            "Prefer list_slides_sections + replace_in_slides_deck / "
            "write_slides_section for edits. Do not rewrite the whole file. "
            "You are editing the open presentation; do not ask which deck."
        ),
    }


def slides_tools() -> list[BaseTool]:
    @tool
    def list_slides_projects() -> dict[str, Any]:
        """List Slides projects in the workspace monorepo (branches slides/<slug>).

        When a deck is already open in the Slides UI, prefer that open slug from
        context instead of asking the user which deck to edit.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        open_slug = slides_active_slug.get()
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
                        "is_open": bool(open_slug and open_slug == slug),
                    }
                )
            out: dict[str, Any] = {"projects": projects}
            if open_slug:
                out["open_slug"] = open_slug
                out["note"] = (
                    f"The user already has '{open_slug}' open. "
                    "Edit that deck; do not ask which presentation."
                )
            return out
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def list_slides_sections(slug: str = "") -> dict[str, Any]:
        """List ``<section>`` slides in a deck (index, id, title). Prefer this over reading the full HTML.

        Omit slug when a deck is open in the Slides UI; the open deck is used.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            html, source = _load_deck_text(resolved)
            if isinstance(html, dict):
                return html
            _prefix, sections, _suffix = _split_sections(html)
            return {
                **_open_deck_note(resolved),
                "slug": resolved,
                "path": _deck_path(resolved),
                "source": source,
                "section_count": len(sections),
                "chars": len(html),
                "sections": [_section_meta(i, sec) for i, sec in enumerate(sections)],
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def read_slides_section(
        slug: str = "",
        index: int | None = None,
        section_id: str | None = None,
    ) -> dict[str, Any]:
        """Read one slide ``<section>`` by index or id. Embedded data-URLs are redacted.

        Omit slug when a deck is open in the Slides UI.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            html, source = _load_deck_text(resolved)
            if isinstance(html, dict):
                return html
            _prefix, sections, _suffix = _split_sections(html)
            resolved_idx = _resolve_section_index(sections, index, section_id)
            if isinstance(resolved_idx, dict):
                return resolved_idx
            section_html = sections[resolved_idx]
            redacted, n_assets = _redact_data_urls(section_html)
            meta = _section_meta(resolved_idx, section_html)
            return {
                **_open_deck_note(resolved),
                "slug": resolved,
                "path": _deck_path(resolved),
                "source": source,
                **meta,
                "html": redacted,
                "note": (
                    f"Redacted {n_assets} embedded data-URL asset(s). "
                    "Use replace_in_slides_deck for text edits; "
                    "use write_slides_section to replace this section only."
                ),
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def write_slides_section(
        html: str,
        slug: str = "",
        index: int | None = None,
        section_id: str | None = None,
        message: str = "Update slides section via Abi",
    ) -> dict[str, Any]:
        """Replace one slide ``<section>`` by index or id. Prefer over rewriting the whole deck.

        Omit slug when a deck is open. Pass the full ``<section>...</section>``
        for that slide. If html still contains ``[REDACTED_DATA_URL]`` placeholders
        from a prior read, original embedded assets are restored automatically.
        """
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
            original, _source = _load_deck_text(resolved)
            if isinstance(original, dict):
                return original
            prefix, sections, suffix = _split_sections(original)
            resolved_idx = _resolve_section_index(sections, index, section_id)
            if isinstance(resolved_idx, dict):
                return resolved_idx
            restored = _restore_redacted_data_urls(html.strip(), sections[resolved_idx])
            sections[resolved_idx] = restored
            new_html = prefix + "".join(sections) + suffix
            if _MAIN_RE.search(original) and not _MAIN_RE.search(new_html):
                return {"error": "Refusing to write: reconstructed HTML lost <main>."}
            result = _persist_deck(
                resolved, new_html, message or "Update slides section via Abi"
            )
            result["section_index"] = resolved_idx
            result.update(_open_deck_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def replace_in_slides_deck(
        old: str,
        new: str,
        slug: str = "",
        occurrence: int = 0,
        message: str = "Replace text in slides deck via Abi",
    ) -> dict[str, Any]:
        """Surgically replace a string in the open deck without dumping full HTML in chat.

        Omit slug when a deck is open in the Slides UI. occurrence: 0 replaces all
        matches; 1 replaces the first, 2 the second, etc. Ideal for small copy
        edits (e.g. change the title on the cover slide).
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        if not old:
            return {"error": "old must be a non-empty string"}
        try:
            html, source = _load_deck_text(resolved)
            if isinstance(html, dict):
                return html
            count = html.count(old)
            if count == 0:
                return {
                    "error": "old string not found in deck",
                    "source": source,
                    "hint": (
                        "Try list_slides_sections + read_slides_section to locate "
                        "exact text (entities like &amp; matter)."
                    ),
                }
            if occurrence < 0:
                return {"error": "occurrence must be >= 0 (0 = all)"}
            if occurrence == 0:
                updated = html.replace(old, new)
                replaced = count
            else:
                if occurrence > count:
                    return {
                        "error": f"occurrence {occurrence} out of range ({count} match(es))"
                    }
                start = -1
                for _ in range(occurrence):
                    start = html.find(old, start + 1)
                updated = html[:start] + new + html[start + len(old) :]
                replaced = 1
            result = _persist_deck(
                resolved, updated, message or "Replace text in slides deck via Abi"
            )
            result["matches_found"] = count
            result["replacements"] = replaced
            result["read_source"] = source
            result.update(_open_deck_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def read_slides_deck(slug: str = "", include_assets: bool = False) -> dict[str, Any]:
        """Read the HTML deck for a Slides project slug.

        Omit slug when a deck is open. By default, heavy scripts and embedded
        data-URLs are redacted. Prefer list_slides_sections / read_slides_section /
        replace_in_slides_deck for edits.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        resolved = _resolve_slug(slug)
        if isinstance(resolved, dict):
            return resolved
        try:
            html, source = _load_deck_text(resolved)
            if isinstance(html, dict):
                return html
            if include_assets:
                return {
                    **_open_deck_note(resolved),
                    "slug": resolved,
                    "path": _deck_path(resolved),
                    "source": source,
                    "html": html,
                    "chars": len(html),
                    "warning": (
                        "Full deck with scripts/assets. This can exceed model "
                        "context limits. Prefer section tools for edits."
                    ),
                }
            view = _view_for_llm(html)
            return {
                **_open_deck_note(resolved),
                "slug": resolved,
                "path": _deck_path(resolved),
                "source": source,
                **view,
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def write_slides_deck(
        html: str,
        slug: str = "",
        message: str = "Update slides deck via Abi",
    ) -> dict[str, Any]:
        """Write the full HTML deck. Avoid for small edits.

        Omit slug when a deck is open. Prefer replace_in_slides_deck or
        write_slides_section.
        """
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
                    "overwrite deck scripts. Use replace_in_slides_deck or "
                    "write_slides_section instead."
                )
            }
        try:
            original = ""
            try:
                loaded, _source = _load_deck_text(resolved)
                if isinstance(loaded, str):
                    original = loaded
            except Exception:  # noqa: BLE001
                original = ""
            content = (
                _restore_redacted_data_urls(html, original) if original else html
            )
            result = _persist_deck(
                resolved, content, message or "Update slides deck via Abi"
            )
            result.update(_open_deck_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def slides_history(slug: str = "", limit: int = 10) -> dict[str, Any]:
        """List recent commits on a Slides project branch (Forgejo version history)."""
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
                **_open_deck_note(resolved),
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
            return {"error": str(exc)}

    return [
        list_slides_projects,
        list_slides_sections,
        read_slides_section,
        write_slides_section,
        replace_in_slides_deck,
        read_slides_deck,
        write_slides_deck,
        slides_history,
    ]
