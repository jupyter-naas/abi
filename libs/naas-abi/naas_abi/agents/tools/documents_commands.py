"""Document commands on git-backed HTML.

Modeled on Google Docs ``documents.batchUpdate`` request types, ODF text
insert-relative-to-paragraph, and Pandoc block constructors (Para, Header).
Storage stays HTML. Positions are heading indexes, not UTF-16 offsets.

See ``naas_abi/apps/nexus/apps/api/app/services/documents/COMMANDS.md``.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

PAGE_BREAK_HTML = '<div class="page-break" data-nexus-page-break></div>'

_HEADING_RE = re.compile(r"<h([1-3])\b[^>]*>(.*?)</h\1>", re.IGNORECASE | re.DOTALL)
_HEADING_TAG_RE = re.compile(r"<h([1-3])\b[^>]*>.*?</h\1>", re.IGNORECASE | re.DOTALL)
_BOUNDARY_RE = re.compile(
    r"<h[1-3]\b|"
    r"<(?:div\b[^>]*(?:data-nexus-page-break|class=[\"'][^\"']*\bpage-break))|"
    r"<footer\b|"
    r"</section>|</main>",
    re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_TITLE_TAG_RE = re.compile(r"<title\b[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
_H1_OPEN_RE = re.compile(r"<h1\b[^>]*>", re.IGNORECASE)
_H1_FULL_RE = re.compile(r"<h1\b[^>]*>.*?</h1>", re.IGNORECASE | re.DOTALL)
_DOC_BODY_OPEN_RE = re.compile(
    r"<div\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bdoc-body\b[^\"']*[\"'][^>]*>",
    re.IGNORECASE,
)
_FOOTER_TITLE_RE = re.compile(
    r'(<span\b[^>]*\bclass="[^"]*\bdoc-footer-title\b[^"]*"[^>]*>)(.*?)(</span>)',
    re.IGNORECASE | re.DOTALL,
)
_PALETTE_CLASS_RE = re.compile(
    r"<[a-z][a-z0-9]*\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bpalette\b[^\"']*[\"']",
    re.IGNORECASE,
)
_SEED_HEADING_RE = re.compile(
    r"<h2\b[^>]*>\s*(Discussion|Findings)\s*</h2>",
    re.IGNORECASE,
)
_SWATCH_HEX_RE = re.compile(
    r"#(?:464B4B|0072CE|171C8F|4AA7B7|27B093|5D93CD|B1B3B3|F4F4F4)",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"<section\b[^>]*>.*?</section>", re.IGNORECASE | re.DOTALL)
_VOID_TAGS = frozenset(
    {
        "area",
        "base",
        "br",
        "col",
        "embed",
        "hr",
        "img",
        "input",
        "link",
        "meta",
        "param",
        "source",
        "track",
        "wbr",
    }
)

# Instructional seed copy. Real topic words like "Findings" stay off this list.
SEED_PLACEHOLDER_PHRASES = (
    "Industry or service line",
    "State the situation",
    "Develop the argument here",
    "First point, written as a complete sentence",
    "Second point, written as a complete sentence",
    "Third point, written as a complete sentence",
    "Replace with the working premise",
    "Replace with the limit that shapes the work",
    "Replace with the choice the reader must make",
    "Document title, industry or service line",
    "Two official table styles",
    "Do not put confidential figures in a seed",
    "Header text alternates",
    "Use the Quote style",
    "Heading 2 stays",
    "Heading 3 uses",
    "Non shaded",
    "Shaded",
    "Supporting detail",
    "A narrower point",
    "in a few sentences so the reader can scan",
    "Keep paragraphs short",
    "This heading uses the official",
    "Body copy stays Outer Space",
    "the page before the body",
    "Secondary colours are for charts",
    "14pt True Blue",
    "must stand apart from the body",
    "Hyperlinks in copy look like",
    "Replace the labels",
)

KNOWN_COMMANDS = frozenset(
    {
        "insert_text",
        "insert_paragraph",
        "insert_heading",
        "insert_page_break",
        "delete_range",
        "replace_text",
        "replace_class",
        "update_paragraph_style",
        "update_title",
        "rename_document",
    }
)

_STYLE_TO_TAG = {
    "heading1": "h1",
    "h1": "h1",
    "title": "h1",
    "heading2": "h2",
    "h2": "h2",
    "heading3": "h3",
    "h3": "h3",
    "paragraph": "p",
    "normal": "p",
    "p": "p",
}


def _strip_tags(raw: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", raw or "")).strip()


def _escape(text: str) -> str:
    return html_lib.escape(text or "", quote=False)


def heading_outline(html: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if not html:
        return items
    for i, match in enumerate(_HEADING_RE.finditer(html)):
        title = html_lib.unescape(_strip_tags(match.group(2)))
        items.append(
            {
                "index": i,
                "title": title or f"Heading {i + 1}",
                "tag": f"h{match.group(1)}",
                "id": None,
                "layout": "cover" if i == 0 else "content",
            }
        )
    return items


def _matching_close_tag(html: str, tag: str, inner_start: int) -> int | None:
    """Start index of the closing tag for an element whose inner HTML starts here."""
    tag_l = (tag or "").lower()
    if not tag_l or tag_l in _VOID_TAGS:
        return None
    open_re = re.compile(rf"<{re.escape(tag)}\b", re.IGNORECASE)
    close_re = re.compile(rf"</{re.escape(tag)}\s*>", re.IGNORECASE)
    depth = 1
    pos = inner_start
    while pos < len(html):
        opened = open_re.search(html, pos)
        closed = close_re.search(html, pos)
        if not closed:
            return None
        if opened and opened.start() < closed.start():
            depth += 1
            pos = opened.end()
            continue
        depth -= 1
        if depth == 0:
            return closed.start()
        pos = closed.end()
    return None


def _doc_body_ranges(html: str) -> list[tuple[int, int]]:
    """``(inner_start, close_start)`` for each ``.doc-body``."""
    ranges: list[tuple[int, int]] = []
    if not html:
        return ranges
    for match in _DOC_BODY_OPEN_RE.finditer(html):
        close = _matching_close_tag(html, "div", match.end())
        if close is not None:
            ranges.append((match.end(), close))
    return ranges


def _insert_at(html: str, at: int, markup: str) -> str:
    injected = markup if markup.endswith("\n") else f"{markup}\n"
    return f"{html[:at]}\n{injected}{html[at:]}"


def _clamp_insert_into_doc_body(html: str, at: int) -> int:
    """Keep inserts inside ``.doc-body``. Never after a footer."""
    bodies = _doc_body_ranges(html)
    if bodies:
        for start, close in bodies:
            if start <= at <= close:
                return at
        chosen = bodies[0]
        for start, close in bodies:
            if start <= at:
                chosen = (start, close)
        return chosen[1]
    footer_at = html[:at].lower().rfind("<footer")
    if footer_at >= 0:
        return footer_at
    return at


def leftover_placeholders(html: str) -> list[str]:
    """Seed phrases still sitting in the stored HTML."""
    if not html:
        return []
    found = [phrase for phrase in SEED_PLACEHOLDER_PHRASES if phrase in html]
    if _PALETTE_CLASS_RE.search(html):
        found.append("colour palette")
    if _SWATCH_HEX_RE.search(html) and "colour palette" not in found:
        found.append("swatch hex")
    for match in _SEED_HEADING_RE.finditer(html):
        title = match.group(1).strip()
        if title not in found:
            found.append(title)
    return found


def leftover_write_note(html: str) -> dict[str, Any]:
    """Tool-result fields so a fill turn cannot treat leftovers as done."""
    leftovers = leftover_placeholders(html)
    note: dict[str, Any] = {"leftover_placeholders": leftovers}
    if leftovers:
        note["incomplete"] = True
        note["warning"] = (
            "INCOMPLETE: seed placeholder copy remains: "
            + ", ".join(leftovers)
            + ". Call apply_document_commands once with replace_text or "
            "replace_class for every remaining slot. Do not reread. Do not stop."
        )
    return note


def _relocate_stray_in_section(section: str) -> str:
    footer_close = re.search(r"</footer>", section, re.IGNORECASE)
    section_close = re.search(r"</section>\s*$", section, re.IGNORECASE)
    if not footer_close or not section_close:
        return section
    stray = section[footer_close.end() : section_close.start()]
    if not stray.strip():
        return section
    bodies = _doc_body_ranges(section)
    if bodies:
        close = bodies[-1][1]
        return (
            f"{section[:close]}{stray}{section[close : footer_close.end()]}"
            f"{section[section_close.start() :]}"
        )
    return (
        f"{section[: footer_close.start()]}"
        f'<div class="doc-body">{stray}</div>\n'
        f"{section[footer_close.start() : section_close.start()]}"
        f"{section[section_close.start() :]}"
    )


def normalize_document_flow(html: str) -> str:
    """Move prose that landed after a footer back into that page's ``.doc-body``."""
    if not html or "</footer>" not in html.lower():
        return html

    def _replace(match: re.Match[str]) -> str:
        return _relocate_stray_in_section(match.group(0))

    return _SECTION_RE.sub(_replace, html)


def replace_class(html: str, class_name: str, replacement: str) -> str | dict[str, str]:
    """Replace the first element with ``class_name``. Empty replacement deletes it."""
    token = (class_name or "").strip().lstrip(".")
    if not token or not re.fullmatch(r"[A-Za-z][\w-]{0,62}", token):
        return {"error": "class_name is required"}
    safe = re.escape(token)
    open_re = re.compile(
        rf"<([a-z][a-z0-9]*)\b[^>]*\bclass\s*=\s*[\"'][^\"']*\b{safe}\b[^\"']*[\"'][^>]*>",
        re.IGNORECASE,
    )
    match = open_re.search(html or "")
    if not match:
        return {"error": f"No element with class {token!r}"}
    tag = match.group(1)
    start = match.start()
    if tag.lower() in _VOID_TAGS or match.group(0).rstrip().endswith("/>"):
        end = match.end()
    else:
        close = _matching_close_tag(html, tag, match.end())
        if close is None:
            return {"error": f"Unclosed element with class {token!r}"}
        end_match = re.match(rf"</{re.escape(tag)}\s*>", html[close:], re.IGNORECASE)
        end = close + (end_match.end() if end_match else 0)
    return f"{html[:start]}{replacement}{html[end:]}"


def _insert_before_close(html: str, markup: str) -> str:
    bodies = _doc_body_ranges(html)
    if bodies:
        return _insert_at(html, bodies[-1][1], markup)
    footer = html.lower().rfind("<footer")
    if footer >= 0:
        return _insert_at(html, footer, markup)
    close = html.lower().rfind("</section>")
    if close >= 0:
        return f"{html[:close]}{markup}\n{html[close:]}"
    main = html.lower().rfind("</main>")
    if main >= 0:
        return f"{html[:main]}{markup}\n{html[main:]}"
    return f"{html}{markup}"


def insert_after_heading_block(html: str, after_heading: int, markup: str) -> str:
    if not html or not markup:
        return html
    ends = [match.end() for match in _HEADING_TAG_RE.finditer(html)]
    if not ends:
        return _insert_before_close(html, markup)
    if after_heading < 0:
        idx = len(ends) - 1
    else:
        idx = max(0, min(after_heading, len(ends) - 1))
    start = ends[idx]
    rest = html[start:]
    boundary = _BOUNDARY_RE.search(rest)
    at = start + (boundary.start() if boundary else len(rest))
    at = _clamp_insert_into_doc_body(html, at)
    return _insert_at(html, at, markup)


def insert_page_break(html: str, after_heading: int = -1) -> str:
    return insert_after_heading_block(html, after_heading, PAGE_BREAK_HTML)


def insert_heading(html: str, title: str = "Heading", level: int = 2, after_heading: int = -1) -> str:
    tag = min(3, max(1, int(level or 2)))
    return insert_after_heading_block(
        html,
        after_heading,
        f"<h{tag}>{_escape(title or 'Heading')}</h{tag}>\n<p></p>",
    )


def insert_paragraph(html: str, text: str = "", after_heading: int = -1) -> str:
    return insert_after_heading_block(html, after_heading, f"<p>{_escape(text)}</p>")


def insert_text(html: str, text: str, after_heading: int = -1) -> str:
    """Google Docs insertText analog: text becomes a paragraph in the HTML store."""
    return insert_paragraph(html, text, after_heading)


def delete_heading_range(html: str, heading_index: int) -> str | dict[str, str]:
    matches = list(_HEADING_TAG_RE.finditer(html or ""))
    if not matches:
        return {"error": "No headings to delete."}
    if heading_index < 0 or heading_index >= len(matches):
        return {"error": f"heading_index out of range (0..{len(matches) - 1})"}
    if len(matches) <= 1:
        return {"error": "Cannot delete the last heading block."}
    start = matches[heading_index].start()
    if heading_index + 1 < len(matches):
        end = matches[heading_index + 1].start()
    else:
        close = re.search(r"</section>|</main>", html[start:], re.IGNORECASE)
        end = start + close.start() if close else len(html)
    return html[:start] + html[end:]


def replace_text(html: str, find: str, replace: str) -> str | dict[str, str]:
    if not find:
        return {"error": "find is required"}
    if find not in html:
        return {"error": f"Text not found: {find!r}"}
    return html.replace(find, replace)


def update_document_title(html: str, title: str) -> str | dict[str, str]:
    """Set the tab ``<title>`` and the first cover ``<h1>`` to the same name.

    ``update_title`` and ``rename_document`` share this HTML step. The project
    display name (sidebar folder) is applied by the wrapper, not here.
    """
    clean = (title or "").strip()
    if not clean:
        return {"error": "title is required"}
    safe = _escape(clean)
    next_html = html or ""
    changed = False
    if _TITLE_TAG_RE.search(next_html):
        next_html = _TITLE_TAG_RE.sub(f"<title>{safe}</title>", next_html, count=1)
        changed = True
    h1_open = _H1_OPEN_RE.search(next_html)
    if h1_open:
        next_html = _H1_FULL_RE.sub(f"{h1_open.group(0)}{safe}</h1>", next_html, count=1)
        changed = True
    if _FOOTER_TITLE_RE.search(next_html):
        next_html = _FOOTER_TITLE_RE.sub(rf"\g<1>{safe}\g<3>", next_html)
        changed = True
    if not changed:
        return {"error": "No document title or cover heading to update."}
    return next_html


def last_rename_document_title(requests: list[dict[str, Any]]) -> str:
    """Last ``rename_document`` title in a command batch, or empty."""
    title = ""
    for raw in requests:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("type") or "").strip().lower() != "rename_document":
            continue
        candidate = str(raw.get("title") or raw.get("text") or "").strip()
        if candidate:
            title = candidate
    return title


def update_paragraph_style(
    html: str, heading_index: int, style: str
) -> str | dict[str, str]:
    tag = _STYLE_TO_TAG.get((style or "").strip().lower())
    if not tag:
        return {
            "error": (
                f"Unknown style {style!r}. Use heading1, heading2, heading3, or paragraph."
            )
        }
    matches = list(_HEADING_RE.finditer(html or ""))
    if not matches:
        return {"error": "No headings to style."}
    if heading_index < 0 or heading_index >= len(matches):
        return {"error": f"heading_index out of range (0..{len(matches) - 1})"}
    match = matches[heading_index]
    inner = match.group(2)
    replacement = f"<{tag}>{inner}</{tag}>"
    return html[: match.start()] + replacement + html[match.end() :]


def apply_document_commands(
    html: str, requests: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply an ordered list of document commands. Atomic: first error aborts."""
    if not isinstance(requests, list) or not requests:
        return {"error": "requests must be a non-empty list of command objects"}
    next_html = html
    applied: list[str] = []
    heading_index = 0
    for i, raw in enumerate(requests):
        if not isinstance(raw, dict):
            return {"error": f"requests[{i}] must be an object with type"}
        typ = str(raw.get("type") or "").strip().lower()
        if typ not in KNOWN_COMMANDS:
            return {
                "error": (
                    f"Unknown command {typ!r}. Use {', '.join(sorted(KNOWN_COMMANDS))}."
                )
            }
        after = raw.get("after_heading", -1)
        try:
            after = int(after)
        except (TypeError, ValueError):
            return {"error": f"requests[{i}].after_heading must be an integer"}
        target = raw.get("heading_index", max(after, 0))
        try:
            target = int(target)
        except (TypeError, ValueError):
            return {"error": f"requests[{i}].heading_index must be an integer"}

        result: str | dict[str, str]
        if typ in {"insert_text", "insert_paragraph"}:
            result = insert_paragraph(next_html, str(raw.get("text") or ""), after)
            outline = heading_outline(result)
            heading_index = after + 1 if after >= 0 else max(0, len(outline) - 1)
        elif typ == "insert_heading":
            level = raw.get("level", 2)
            try:
                level = int(level)
            except (TypeError, ValueError):
                return {"error": f"requests[{i}].level must be an integer"}
            result = insert_heading(
                next_html,
                title=str(raw.get("title") or raw.get("text") or "Heading"),
                level=level,
                after_heading=after,
            )
            outline = heading_outline(result)
            heading_index = min(after + 1 if after >= 0 else len(outline) - 1, len(outline) - 1)
        elif typ == "insert_page_break":
            result = insert_page_break(next_html, after)
            heading_index = max(after, 0)
        elif typ == "delete_range":
            result = delete_heading_range(next_html, target)
            if isinstance(result, str):
                heading_index = max(0, target - 1)
        elif typ == "replace_text":
            result = replace_text(
                next_html, str(raw.get("find") or ""), str(raw.get("replace") or "")
            )
            heading_index = target
        elif typ == "replace_class":
            result = replace_class(
                next_html,
                str(raw.get("class_name") or raw.get("find") or ""),
                str(raw.get("replace") or raw.get("html") or raw.get("text") or ""),
            )
            heading_index = target
        elif typ == "update_paragraph_style":
            result = update_paragraph_style(
                next_html, target, str(raw.get("style") or "")
            )
            heading_index = target
        elif typ in {"update_title", "rename_document"}:
            result = update_document_title(
                next_html, str(raw.get("title") or raw.get("text") or "")
            )
            heading_index = 0
        else:
            return {"error": f"Unhandled command {typ!r}"}

        if isinstance(result, dict):
            return result
        next_html = result
        applied.append(typ)

    next_html = normalize_document_flow(next_html)
    outline = heading_outline(next_html)
    if heading_index >= len(outline):
        heading_index = max(0, len(outline) - 1)
    return {
        "ok": True,
        "html": next_html,
        "applied": applied,
        "outline": outline,
        "heading_index": heading_index,
        "heading_count": len(outline),
        "section_index": heading_index,
        "section_count": len(outline),
        "ids": [None] * len(outline),
        "sections": outline,
        **leftover_write_note(next_html),
    }
