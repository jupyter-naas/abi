"""Abi tools for Nexus Slides projects.

Prefer the Coder workspace sidecar filesystem when a slides runtime is bound
to the request (Continue-parity). Fall back to Forgejo with an explicit note.

Decks live at ``slides/<slug>/deck.html`` on branch ``slides/<slug>``. When the
user has a deck open in Nexus, ``slides_active_slug`` is set so tools default
to that deck and Abi must not ask which presentation to edit.

Template decks keep slide markup in ``<main>`` (~tens of KB) but also ship
inline asset ``<script>`` blobs (~1MB with base64 images). PPTX export walks
the live ``.slide`` DOM; tools therefore:

- expose section-scoped read/write and surgical string replace
- redact heavy scripts / data-URLs on full-deck reads
- never require the model to edit ``buildPptx`` or ``FOOTER_TXT``
"""

from __future__ import annotations

import html as html_lib
import json
import re
from typing import Any

from langchain_core.tools import BaseTool, tool
from naas_abi.agents.slides_policy import reject_unresearched_slides_write
from naas_abi_core.services.agent.context import (
    agent_user_id,
    agent_workspace_id,
    coder_workspace_base,
    slides_active_mode,
    slides_active_slug,
    slides_active_title,
)
from naas_abi_core.services.agent.tools.workspace_tools import _call as _sidecar_call
from naas_abi_core.services.source_control.SourceControlPorts import (
    BranchNameConflictError,
    SourceControlError,
)

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
_REPO_ID_RE = re.compile(r"^[A-Za-z0-9._-]+/[A-Za-z0-9._-]+$")
_WIPED_DECK_ERROR = "API restart wiped this deck. Click New, then retry."


def _get_source_control():
    from naas_abi import ABIModule

    return ABIModule.get_instance().engine.services.source_control


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
    if raw.startswith(f"{repo_id}:") or raw.startswith(f"{repo_id}@"):
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
        return "Forgejo is not reachable. Slides needs git storage."
    if _is_repo_id_message(text) or "deck.html" in lowered:
        return _WIPED_DECK_ERROR
    return text


def _tool_error(exc: BaseException) -> dict[str, Any]:
    return {"error": _friendly_sc_error(exc)}


def _load_seed_deck_html() -> str | None:
    """Same Minimal Light seed the UI New path writes."""
    try:
        from importlib import resources

        root = resources.files("naas_abi.apps.nexus.assets.slides.templates")
        text = (root / "minimal-light-v1.html").read_text(encoding="utf-8")
        return text if text.strip() else None
    except Exception:  # noqa: BLE001
        return None


def _looks_like_missing_deck(exc: BaseException, paths: dict[str, str]) -> bool:
    text = str(exc)
    deck = paths.get("deck_path") or ""
    if deck and deck in text:
        return True
    return _is_repo_id_message(text)


def _ensure_project_json(
    sc: Any, repo_id: str, paths: dict[str, str], slug: str
) -> None:
    """Preview GET resolves the project via project.json; writes must seed it."""
    try:
        existing = sc.get_file(
            repo_id=repo_id, path=paths["project_path"], ref=paths["branch"]
        )
        if existing.text:
            return
    except SourceControlError:
        pass
    ws = _workspace_id()
    title = (slides_active_title.get() or "").strip() or slug.replace("-", " ").title()
    meta = {
        "slug": slug,
        "workspace_id": ws or "",
        "title": title,
        "template_id": "minimal-light-v1",
    }
    try:
        sc.upsert_file(
            repo_id=repo_id,
            path=paths["project_path"],
            content=json.dumps(meta, indent=2) + "\n",
            message=f"Seed slides project {slug}",
            branch=paths["branch"],
        )
    except SourceControlError:
        pass


def _ensure_slides_write_paths(slug: str) -> dict[str, str]:
    """Repo + slides branch + project.json, matching the UI create path."""
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
    _ensure_project_json(sc, repo_id, paths, slug)
    return paths


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


def _deck_path(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"slides/{_workspace_segment(ws)}/{slug}/deck.html"
    return f"slides/{slug}/deck.html"


def _legacy_deck_path(slug: str) -> str:
    return f"slides/{slug}/deck.html"


def _project_path(slug: str, workspace_id: str | None = None) -> str:
    ws = workspace_id or _workspace_id()
    if ws:
        return f"slides/{_workspace_segment(ws)}/{slug}/project.json"
    return f"slides/{slug}/project.json"


def _legacy_project_path(slug: str) -> str:
    return f"slides/{slug}/project.json"


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
                "deck_path": _deck_path(slug, ws),
                "project_path": _project_path(slug, ws),
            }
    legacy = _legacy_branch(slug)
    if legacy in names:
        # Fail closed: legacy decks require a verified matching owner.
        if not ws:
            return {"error": f"slides project {slug} not in this workspace"}
        try:
            meta = sc.get_file(
                repo_id=repo_id, path=_legacy_project_path(slug), ref=legacy
            )
            data = json.loads(meta.text or "{}") if meta.text else {}
            owner = str(data.get("workspace_id") or "").strip()
            if owner != ws:
                return {"error": f"slides project {slug} not in this workspace"}
        except (SourceControlError, json.JSONDecodeError):
            return {"error": f"slides project {slug} not in this workspace"}
        return {
            "branch": legacy,
            "deck_path": _legacy_deck_path(slug),
            "project_path": _legacy_project_path(slug),
        }
    if ws:
        # Default to namespaced location for new writes.
        return {
            "branch": _branch(slug, ws),
            "deck_path": _deck_path(slug, ws),
            "project_path": _project_path(slug, ws),
        }
    return {
        "branch": legacy,
        "deck_path": _legacy_deck_path(slug),
        "project_path": _legacy_project_path(slug),
    }


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
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "sidecar"}
    result = _sidecar_call("read_file", {"path": paths["deck_path"]})
    if result.get("error"):
        return {"error": result["error"], "source": "sidecar"}
    if result.get("binary"):
        return {"error": "Deck is not UTF-8 text", "source": "sidecar"}
    content = result.get("content")
    if not isinstance(content, str):
        return {"error": "Sidecar read returned no content", "source": "sidecar"}
    return content


def _write_deck_via_sidecar(slug: str, html: str) -> dict[str, Any]:
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "sidecar"}
    result = _sidecar_call(
        "write_file", {"path": paths["deck_path"], "content": html}
    )
    if result.get("error") or result.get("ok") is False:
        return {
            "error": result.get("error") or "sidecar write failed",
            "source": "sidecar",
        }
    return {
        "ok": True,
        "slug": slug,
        "path": paths["deck_path"],
        "source": "sidecar",
        "bytes": result.get("bytes"),
    }


def _load_deck_via_forgejo(slug: str) -> str | dict[str, Any]:
    paths = _resolve_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "forgejo"}
    sc = _get_source_control()
    try:
        file = sc.get_file(
            repo_id=_repo_id(), path=paths["deck_path"], ref=paths["branch"]
        )
    except SourceControlError as exc:
        if _looks_like_missing_deck(exc, paths):
            seed = _load_seed_deck_html()
            if seed:
                return seed
            return {"error": _WIPED_DECK_ERROR, "source": "forgejo"}
        return {"error": _friendly_sc_error(exc), "source": "forgejo"}
    if file.is_binary or file.text is None:
        return {"error": "Deck is not UTF-8 text", "source": "forgejo"}
    return file.text


def _commit_deck_forgejo(slug: str, html: str, message: str) -> dict[str, Any]:
    paths = _ensure_slides_write_paths(slug)
    if paths.get("error"):
        return {"error": paths["error"], "source": "forgejo"}
    sc = _get_source_control()
    try:
        commit = sc.upsert_file(
            repo_id=_repo_id(),
            path=paths["deck_path"],
            content=html,
            message=message,
            branch=paths["branch"],
        )
    except SourceControlError as exc:
        return {"error": _friendly_sc_error(exc), "source": "forgejo"}
    return {
        "slug": slug,
        "path": paths["deck_path"],
        "branch": paths["branch"],
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
    """Write editing context (sidecar) then version storage (Forgejo).

    Product truth when the slides runtime is up: Coder/sidecar is the live
    editing copy. Forgejo is the commit/history snapshot (Save + dual-write).
    """
    sources: list[str] = []
    sidecar_result: dict[str, Any] | None = None
    if _sidecar_available():
        sidecar_result = _write_deck_via_sidecar(slug, html)
        if sidecar_result.get("ok"):
            sources.append("sidecar")
        else:
            # Keep going: Forgejo write still updates version storage.
            sources.append("sidecar-failed")
    try:
        forgejo = _commit_deck_forgejo(slug, html, message)
        if forgejo.get("error"):
            if sidecar_result and sidecar_result.get("ok"):
                return {
                    **sidecar_result,
                    "sources": sources,
                    "forgejo_error": forgejo.get("error"),
                    "note": (
                        "Updated Coder workspace (live edit); Forgejo snapshot failed. "
                        "Preview should follow sidecar. Use File → Save later for history."
                    ),
                }
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
        return result
    except Exception as exc:  # noqa: BLE001
        if sidecar_result and sidecar_result.get("ok"):
            return {
                **sidecar_result,
                "sources": sources,
                "forgejo_error": _friendly_sc_error(exc),
                "note": (
                    "Updated Coder workspace (live edit); Forgejo snapshot failed. "
                    "Preview should follow sidecar. Use File → Save later for history."
                ),
            }
        return {"error": _friendly_sc_error(exc), "sources": sources}


def _replace_string_pairs(old: str, new: str) -> list[tuple[str, str]]:
    """Return (old, new) pairs covering plain text and HTML-entity forms.

    Cover titles in deck HTML use ``&amp;`` while PPTX script strings use raw
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

    Searching for ``—`` or ``&mdash;`` (after unescape) must match deck HTML
    that stores ``&mdash;``, ``&#8212;``, or the literal Unicode dash. Same for
    ``&`` / ``&amp;`` so cover ``<h1>`` text updates with PPTX script strings.
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
    """Visible cover title: first section ``<h1>``, else first deck ``<h1>``."""
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
            "error": "old string not found in deck",
            "hint": (
                "Try list_slides_sections + read_slides_section to locate "
                "exact text (tools also match HTML entities like &amp;, "
                "&mdash;, &#8212;). For cover/title edits on slide 1, pass "
                "section_index=0."
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
    """Replace within one ``<section>`` when scoped; else whole deck.

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
            "error": "Deck has no <section> slides to scope the replace into.",
            "hint": "Omit section_index/section_id to replace across the whole deck.",
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
    _prefix, sections, _suffix = _split_sections(html)
    return {
        "html": redacted,
        "chars": len(html),
        "chars_redacted": len(redacted),
        "section_count": len(sections),
        "redacted_scripts": n_scripts,
        "redacted_assets": n_assets,
        "note": (
            "Heavy <script> blocks (assets / export) and data-URLs are redacted. "
            "Prefer list_slides_sections + replace_in_slides_deck / "
            "write_slides_section for HTML edits. Do not rewrite the whole file "
            "or edit buildPptx. Preview is HTML; PPTX is derived at export. "
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
                        # Unscoped legacy: hide until claimed via Slides UI.
                        continue
                except (SourceControlError, json.JSONDecodeError):
                    if ws and "/" not in name[len(_BRANCH_PREFIX) :]:
                        continue
                projects.append(
                    {
                        "slug": slug,
                        "title": title,
                        "branch": branch.name,
                        "deck_path": (
                            _deck_path(slug, ws)
                            if ns_prefix and name.startswith(ns_prefix)
                            else _legacy_deck_path(slug)
                        ),
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
            return _tool_error(exc)

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
            return _tool_error(exc)

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
            return _tool_error(exc)

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

        For news, current events, or factual briefs: call web_search first.
        This tool rejects the write until search has run this turn.
        """
        blocked = reject_unresearched_slides_write()
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
            return _tool_error(exc)

    @tool
    def replace_in_slides_deck(
        old: str,
        new: str,
        slug: str = "",
        occurrence: int = 0,
        section_index: int | None = None,
        section_id: str | None = None,
        message: str = "Replace text in slides deck via Abi",
    ) -> dict[str, Any]:
        """Surgically replace a string in the open deck without dumping full HTML in chat.

        Omit slug when a deck is open in the Slides UI. occurrence: 0 replaces all
        matches; 1 replaces the first, 2 the second, etc. Matches HTML entities
        flexibly (``&``/``&amp;``, ``—``/``&mdash;``/``&#8212;``, ``–``/``&ndash;``)
        so cover ``<h1>`` / subtitle HTML updates. PPTX export reads that live
        DOM; do not edit ``buildPptx`` or ``FOOTER_TXT``.

        For cover / title / \"slide 1\" edits: pass section_index=0 (or
        section_id of the cover) and occurrence=0. Do not use occurrence=1 for
        \"the title\": document order hits ``<title>`` / menubar before the cover
        ``<h1>`` that Preview shows. Confirm ``cover_h1_updated`` /
        ``cover_subtitle_updated`` in the tool result before claiming Preview
        and PPTX changed.

        For news, current events, or factual briefs: call web_search first.
        This tool rejects the write until search has run this turn.
        """
        blocked = reject_unresearched_slides_write()
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
            html, source = _load_deck_text(resolved)
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
            result = _persist_deck(
                resolved, updated, message or "Replace text in slides deck via Abi"
            )
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
            result.update(_open_deck_note(resolved))
            return result
        except Exception as exc:  # noqa: BLE001
            return _tool_error(exc)

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
            return _tool_error(exc)

    @tool
    def write_slides_deck(
        html: str,
        slug: str = "",
        message: str = "Update slides deck via Abi",
    ) -> dict[str, Any]:
        """Write the full HTML deck. Avoid for small edits.

        Omit slug when a deck is open. Prefer replace_in_slides_deck or
        write_slides_section.

        For news, current events, or factual briefs: call web_search first.
        This tool rejects the write until search has run this turn.
        """
        blocked = reject_unresearched_slides_write()
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
            return _tool_error(exc)

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
            return _tool_error(exc)

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
