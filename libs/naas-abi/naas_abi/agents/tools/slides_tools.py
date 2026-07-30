"""Abi tools for Nexus Slides projects (Forgejo-backed decks).

Read/write/list/history against ``slides/<slug>/deck.html`` on branch
``slides/<slug>``. Does not surface Coder workspaces.

Template decks keep slide markup in ``<main>`` (~tens of KB) but also ship
inline PPTX/asset ``<script>`` blobs (~1MB with base64 images). Returning the
raw file into chat overflows mid-size model windows (~256k) and full-deck
rewrites exceed max output tokens. Tools therefore:

- expose section-scoped read/write and surgical string replace
- redact heavy scripts / data-URLs on full-deck reads
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
        # Naive close trim
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


def _load_deck_text(slug: str) -> str | dict[str, Any]:
    sc = _get_source_control()
    file = sc.get_file(repo_id=_repo_id(), path=_deck_path(slug), ref=_branch(slug))
    if file.is_binary or file.text is None:
        return {"error": "Deck is not UTF-8 text"}
    return file.text


def _commit_deck(slug: str, html: str, message: str) -> dict[str, Any]:
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
    }


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
            "write_slides_section for edits. Do not rewrite the whole file."
        ),
    }


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
    def list_slides_sections(slug: str) -> dict[str, Any]:
        """List ``<section>`` slides in a deck (index, id, title). Prefer this over reading the full HTML."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        try:
            html = _load_deck_text(slug)
            if isinstance(html, dict):
                return html
            _prefix, sections, _suffix = _split_sections(html)
            return {
                "slug": slug,
                "path": _deck_path(slug),
                "section_count": len(sections),
                "chars": len(html),
                "sections": [_section_meta(i, sec) for i, sec in enumerate(sections)],
            }
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def read_slides_section(
        slug: str, index: int | None = None, section_id: str | None = None
    ) -> dict[str, Any]:
        """Read one slide ``<section>`` by index or id. Embedded data-URLs are redacted."""
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        try:
            html = _load_deck_text(slug)
            if isinstance(html, dict):
                return html
            _prefix, sections, _suffix = _split_sections(html)
            resolved = _resolve_section_index(sections, index, section_id)
            if isinstance(resolved, dict):
                return resolved
            section_html = sections[resolved]
            redacted, n_assets = _redact_data_urls(section_html)
            meta = _section_meta(resolved, section_html)
            return {
                "slug": slug,
                "path": _deck_path(slug),
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
        slug: str,
        html: str,
        index: int | None = None,
        section_id: str | None = None,
        message: str = "Update slides section via Abi",
    ) -> dict[str, Any]:
        """Replace one slide ``<section>`` by index or id. Prefer over rewriting the whole deck.

        Pass the full ``<section>...</section>`` for that slide. If html still
        contains ``[REDACTED_DATA_URL]`` placeholders from a prior read, original
        embedded assets are restored automatically.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        if not html or not html.strip():
            return {"error": "html must be a non-empty string"}
        if "<section" not in html.lower():
            return {"error": "html must include a <section>...</section> block"}
        try:
            original = _load_deck_text(slug)
            if isinstance(original, dict):
                return original
            prefix, sections, suffix = _split_sections(original)
            resolved = _resolve_section_index(sections, index, section_id)
            if isinstance(resolved, dict):
                return resolved
            restored = _restore_redacted_data_urls(html.strip(), sections[resolved])
            sections[resolved] = restored
            new_html = prefix + "".join(sections) + suffix
            if _MAIN_RE.search(original) and not _MAIN_RE.search(new_html):
                return {"error": "Refusing to write: reconstructed HTML lost <main>."}
            result = _commit_deck(
                slug, new_html, message or "Update slides section via Abi"
            )
            result["section_index"] = resolved
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def replace_in_slides_deck(
        slug: str,
        old: str,
        new: str,
        occurrence: int = 0,
        message: str = "Replace text in slides deck via Abi",
    ) -> dict[str, Any]:
        """Surgically replace a string in the deck without loading/writing the full HTML in chat.

        occurrence: 0 replaces all matches; 1 replaces the first, 2 the second, etc.
        Ideal for small copy edits (e.g. change one word on the cover slide).
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        if not old:
            return {"error": "old must be a non-empty string"}
        try:
            html = _load_deck_text(slug)
            if isinstance(html, dict):
                return html
            count = html.count(old)
            if count == 0:
                return {
                    "error": "old string not found in deck",
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
            result = _commit_deck(
                slug, updated, message or "Replace text in slides deck via Abi"
            )
            result["matches_found"] = count
            result["replacements"] = replaced
            return result
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def read_slides_deck(slug: str, include_assets: bool = False) -> dict[str, Any]:
        """Read the HTML deck for a Slides project slug.

        By default, heavy scripts and embedded data-URLs are redacted to protect
        context limits. Prefer list_slides_sections / read_slides_section /
        replace_in_slides_deck for edits. Set include_assets=true only if you
        truly need the raw file (usually you do not).
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
        try:
            html = _load_deck_text(slug)
            if isinstance(html, dict):
                return html
            if include_assets:
                return {
                    "slug": slug,
                    "path": _deck_path(slug),
                    "html": html,
                    "chars": len(html),
                    "warning": (
                        "Full deck with scripts/assets. This can exceed model "
                        "context limits. Prefer section tools for edits."
                    ),
                }
            view = _view_for_llm(html)
            return {"slug": slug, "path": _deck_path(slug), **view}
        except Exception as exc:  # noqa: BLE001
            return {"error": str(exc)}

    @tool
    def write_slides_deck(
        slug: str, html: str, message: str = "Update slides deck via Abi"
    ) -> dict[str, Any]:
        """Write and commit the full HTML deck. Avoid for small edits.

        Prefer replace_in_slides_deck or write_slides_section. If html contains
        ``[REDACTED_DATA_URL]`` placeholders from read_slides_deck, original
        embedded assets are restored from the current deck before commit.
        Refuses writes that only contain redacted script placeholders (would
        destroy PPTX/asset scripts). Keep buildPptx() in sync when restructuring.
        """
        if not agent_user_id.get():
            return {"error": "No authenticated user on this agent session."}
        if not _SLUG_RE.match(slug or ""):
            return {"error": "Invalid slug (lowercase kebab-case required)."}
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
                loaded = _load_deck_text(slug)
                if isinstance(loaded, str):
                    original = loaded
            except Exception:  # noqa: BLE001
                original = ""
            content = (
                _restore_redacted_data_urls(html, original) if original else html
            )
            return _commit_deck(
                slug, content, message or "Update slides deck via Abi"
            )
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
        list_slides_sections,
        read_slides_section,
        write_slides_section,
        replace_in_slides_deck,
        read_slides_deck,
        write_slides_deck,
        slides_history,
    ]
