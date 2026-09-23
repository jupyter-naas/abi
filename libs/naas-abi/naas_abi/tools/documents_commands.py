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
from urllib.parse import urlsplit

from naas_abi.tools.documents_html import replace_visible, template_fields

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
    r"<h2\b[^>]*>\s*(Discussion|Findings|Ce qui a changé)\s*</h2>",
    re.IGNORECASE,
)
_SLOT_OPEN_RE = re.compile(
    r"<([a-z][a-z0-9]*)\b[^>]*\bdata-slot\s*=\s*[\"']([^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)
_PAGE_SECTION_OPEN_RE = re.compile(
    r"<section\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bpage\b[^\"']*[\"'][^>]*>",
    re.IGNORECASE,
)
_PAGE_BREAK_RE = re.compile(
    r"\s*(?:<div\b[^>]*(?:data-nexus-page-break|class=[\"'][^\"']*\bpage-break)[^>]*>\s*</div>|"
    r"<div\b[^>]*(?:data-nexus-page-break|class=[\"'][^\"']*\bpage-break)[^>]*/>)\s*",
    re.IGNORECASE,
)
_DELETABLE_CLASSES = frozenset({"palette", "decision"})
_SWATCH_HEX_RE = re.compile(
    r"#(?:464B4B|0072CE|171C8F|4AA7B7|27B093|5D93CD|B1B3B3|F4F4F4)",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"<section\b[^>]*>.*?</section>", re.IGNORECASE | re.DOTALL)
_STYLE_OR_SVG_RE = re.compile(
    r"<(style|script|svg)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)
_EMPTY_CLASS_RES = (
    (
        "intro",
        re.compile(
            r"<p\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bintro\b[^\"']*[\"'][^>]*>\s*</p>",
            re.IGNORECASE,
        ),
    ),
    (
        "subtitle",
        re.compile(
            r"<p\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bsubtitle\b[^\"']*[\"'][^>]*>\s*</p>",
            re.IGNORECASE,
        ),
    ),
    (
        "note",
        re.compile(
            r"<p\b[^>]*\bclass\s*=\s*[\"'][^\"']*\bnote\b[^\"']*[\"'][^>]*>\s*</p>",
            re.IGNORECASE,
        ),
    ),
)
_EMPTY_HEADING_RE = re.compile(r"<h[2-4]\b[^>]*>\s*</h[2-4]>", re.IGNORECASE)
_LABEL_ONLY_LEFTOVERS = frozenset({"colour palette", "swatch hex"})
_EMPTY_REPLACE_ERROR = "replace must be non-empty topic copy"
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
    "Heading 1 style",
    "Outer Space. Use it when",
    "Cette note demande une décision",
    "Décision demandée",
    "Les missions reçoivent déjà",
    "Approuver un cadre de réponse unique",
    "Valider le cadre de réponse du cabinet",
    "Les signaux sont publics et simultanés",
    "Quatre expositions, dans cet ordre",
)
_SEED_TH_RE = re.compile(
    r"<th\b[^>]*>\s*(Topic|Owner|Status|Item|Note)\s*</th>",
    re.IGNORECASE,
)
_BLOCK_RE = re.compile(
    r"<(p|li|h[1-4]|td|th|blockquote|span)\b[^>]*>.*?</\1>",
    re.IGNORECASE | re.DOTALL,
)

KNOWN_COMMANDS = frozenset(
    {
        "insert_text",
        "insert_paragraph",
        "insert_heading",
        "insert_page_break",
        "insert_list",
        "insert_table",
        "insert_image",
        "apply_mark",
        "insert_link",
        "insert_comment",
        "insert_suggestion",
        "delete_range",
        "delete_block",
        "replace_text",
        "replace_class",
        "update_paragraph_style",
        "update_title",
        "rename_document",
        "fill_slots",
        "reflow",
    }
)

# Picker names (Normal text, Title, Subtitle, Heading 1/2/3). Title is the
# cover H1. Heading 1 is the official Word section style (h2), not the title.
PARAGRAPH_STYLE_SPECS: dict[str, tuple[str, str]] = {
    "normal": ("p", "fmz-normal"),
    "normal text": ("p", "fmz-normal"),
    "paragraph": ("p", "fmz-normal"),
    "fmz-normal": ("p", "fmz-normal"),
    "fm-normal": ("p", "fmz-normal"),
    "p": ("p", "fmz-normal"),
    "title": ("h1", "fmz-title"),
    "fmz-title": ("h1", "fmz-title"),
    "fm-title": ("h1", "fmz-title"),
    "h1": ("h1", "fmz-title"),
    "subtitle": ("p", "fmz-subtitle"),
    "fmz-subtitle": ("p", "fmz-subtitle"),
    "fm-subtitle": ("p", "fmz-subtitle"),
    "heading1": ("h2", "fmz-heading-1"),
    "heading 1": ("h2", "fmz-heading-1"),
    "fmz-heading-1": ("h2", "fmz-heading-1"),
    "fm-heading-1": ("h2", "fmz-heading-1"),
    "h2": ("h2", "fmz-heading-1"),
    "heading2": ("h3", "fmz-heading-2"),
    "heading 2": ("h3", "fmz-heading-2"),
    "fmz-heading-2": ("h3", "fmz-heading-2"),
    "fm-heading-2": ("h3", "fmz-heading-2"),
    "h3": ("h3", "fmz-heading-2"),
    "heading3": ("h4", "fmz-heading-3"),
    "heading 3": ("h4", "fmz-heading-3"),
    "fmz-heading-3": ("h4", "fmz-heading-3"),
    "fm-heading-3": ("h4", "fmz-heading-3"),
    "h4": ("h4", "fmz-heading-3"),
}
_INSERT_HEADING_STYLES = {
    1: ("h1", "fmz-title"),
    2: ("h2", "fmz-heading-1"),
    3: ("h3", "fmz-heading-2"),
    4: ("h4", "fmz-heading-3"),
}
_PICKER_STYLE_NAMES = "normal, title, subtitle, heading1, heading2, or heading3"


def _strip_tags(raw: str) -> str:
    return re.sub(r"\s+", " ", _TAG_RE.sub("", raw or "")).strip()


def _escape(text: str) -> str:
    return html_lib.escape(text or "", quote=False)


def _attr(value: str) -> str:
    return html_lib.escape(value or "", quote=True)


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


def _prose_html(html: str) -> str:
    """Document copy only: drop CSS, scripts, and SVG so leftover scans stay honest."""
    return _STYLE_OR_SVG_RE.sub("", html or "")


def leftover_placeholders(html: str) -> list[str]:
    """Seed phrases still sitting in the stored HTML."""
    if not html:
        return []
    prose = _prose_html(html)
    found = [phrase for phrase in SEED_PLACEHOLDER_PHRASES if phrase in prose]
    if _PALETTE_CLASS_RE.search(prose):
        found.append("colour palette")
    if _SWATCH_HEX_RE.search(prose) and "colour palette" not in found:
        found.append("swatch hex")
    for match in _SEED_HEADING_RE.finditer(prose):
        title = match.group(1).strip()
        if title not in found:
            found.append(title)
    for match in _SEED_TH_RE.finditer(prose):
        header = match.group(1).strip()
        if header not in found:
            found.append(header)
    for class_name, marker in _EMPTY_CLASS_RES:
        if marker.search(prose):
            label = f"empty {class_name}"
            if label not in found:
                found.append(label)
    if _EMPTY_HEADING_RE.search(prose):
        if "empty heading" not in found:
            found.append("empty heading")
    if re.search(r'data-layout=["\']tables["\']', prose, re.IGNORECASE) and not re.search(
        r"<table\b", prose, re.IGNORECASE
    ):
        if "missing tables" not in found:
            found.append("missing tables")
    return found


FILL_SLOT_KEYS = (
    "title",
    "subtitle",
    "intro",
    "note",
    "situation",
    "quote",
    "sections",
    "tables_heading",
    "tables_intro",
    "tables",
)


def _fill_keys_for_leftover(phrase: str) -> tuple[str, ...]:
    """Map a leftover label onto fill_document_slots keys. Never apply recipes."""
    text = (phrase or "").strip().lower()
    if phrase in _LABEL_ONLY_LEFTOVERS or text == "missing tables":
        return ("tables",)
    if text.startswith("empty "):
        name = text[6:]
        if name in {"intro", "subtitle", "note"}:
            return (name,)
        return ("title", "sections")
    if "quote" in text or "must stand apart" in text:
        return ("quote",)
    if any(
        token in text
        for token in (
            "situation",
            "missions reçoivent",
            "missions recoivent",
        )
    ):
        return ("situation",)
    if any(
        token in text
        for token in (
            "intro",
            "state the situation",
            "scan the page",
            "the page before the body",
            "cette note demande",
        )
    ):
        return ("intro",)
    if any(token in text for token in ("subtitle", "kicker", "industry or service")):
        return ("subtitle",)
    if any(
        token in text
        for token in (
            "header text alternates",
            "body copy stays",
            "secondary colours",
            "14pt true blue",
            "décision demandée",
            "decision demandee",
            "approuver un cadre",
        )
    ):
        return ("note",)
    if "document title" in text or "valider le cadre de réponse" in text:
        return ("title",)
    if text in {"topic", "owner", "status", "item", "note"} or any(
        token in text
        for token in (
            "findings",
            "shaded",
            "assumption",
            "working premise",
            "replace the labels",
            "table",
            "confidential figures",
            "two official table",
        )
    ):
        return ("tables_heading", "tables_intro", "tables")
    return ("sections",)


def leftover_slots(html: str) -> list[str]:
    """Fill keys still open. Not apply_document_commands recipes."""
    keys: list[str] = []
    seen: set[str] = set()
    for phrase in leftover_placeholders(html):
        for key in _fill_keys_for_leftover(phrase):
            if key not in FILL_SLOT_KEYS or key in seen:
                continue
            seen.add(key)
            keys.append(key)
    return keys


def leftover_write_note(html: str) -> dict[str, Any]:
    """Tool-result fields so a fill turn cannot treat leftovers as done."""
    leftovers = leftover_placeholders(html)
    slots = leftover_slots(html)
    note: dict[str, Any] = {
        "leftover_placeholders": leftovers,
        "leftover_slots": slots,
    }
    if leftovers:
        note["incomplete"] = True
        note["warning"] = leftover_followup_warning(leftovers, slots)
        return note
    from naas_abi.agents.documents.policy import documents_fill_count

    if documents_fill_count() >= 1:
        note["warning"] = (
            "Slots are filled. Stop and reply. "
            "Do not call fill_document_slots again this turn."
        )
    return note


def leftover_followup_warning(leftovers: list[str], slots: list[str]) -> str:
    """Invite at most one leftover fill. Never say keep going after a no-op."""
    from naas_abi.agents.documents.policy import documents_fill_count

    phrases = ", ".join(leftovers)
    keys = ", ".join(slots) if slots else "(none)"
    prefix = (
        "Seed placeholder copy remains: "
        + phrases
        + ". leftover_slots keys: "
        + keys
        + ". "
    )
    if documents_fill_count() >= 1:
        return (
            prefix + "Stop and reply. Do not call fill_document_slots again this turn. "
            "leftover_slots wait for a later turn. "
            "Do not call apply_document_commands."
        )
    return (
        prefix + "Call fill_document_slots once with leftover_slots keys, then stop. "
        "Each value must be a non-empty topic sentence. "
        "Do not write the memo only in chat. "
        "Do not call apply_document_commands."
    )


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
    """Move stray footer prose, then remonter le texte on empty letter pages."""
    if html and "</footer>" in html.lower():

        def _replace(match: re.Match[str]) -> str:
            return _relocate_stray_in_section(match.group(0))

        html = _SECTION_RE.sub(_replace, html)
    return reflow_document(html)


def _span_from_open(html: str, match: re.Match[str]) -> tuple[int, int] | None:
    tag = match.group(1)
    start = match.start()
    if tag.lower() in _VOID_TAGS or match.group(0).rstrip().endswith("/>"):
        return start, match.end()
    close = _matching_close_tag(html, tag, match.end())
    if close is None:
        return None
    end_match = re.match(rf"</{re.escape(tag)}\s*>", html[close:], re.IGNORECASE)
    end = close + (end_match.end() if end_match else 0)
    return start, end


def _slot_span(html: str, slot: str) -> tuple[int, int] | None:
    for match in _SLOT_OPEN_RE.finditer(html or ""):
        if match.group(2) == slot:
            return _span_from_open(html, match)
    return None


def _class_span(html: str, class_name: str) -> tuple[int, int] | None:
    token = (class_name or "").strip().lstrip(".")
    if not token:
        return None
    open_re = re.compile(
        rf"<([a-z][a-z0-9]*)\b[^>]*\bclass\s*=\s*[\"'][^\"']*\b{re.escape(token)}\b[^\"']*[\"'][^>]*>",
        re.IGNORECASE,
    )
    match = open_re.search(html or "")
    if not match:
        return None
    return _span_from_open(html, match)


def _page_outer_ranges(html: str) -> list[tuple[int, int]]:
    ranges: list[tuple[int, int]] = []
    for match in _PAGE_SECTION_OPEN_RE.finditer(html or ""):
        close = _matching_close_tag(html, "section", match.end())
        if close is None:
            continue
        end_match = re.match(r"</section\s*>", html[close:], re.IGNORECASE)
        end = close + (end_match.end() if end_match else 0)
        ranges.append((match.start(), end))
    return ranges


def _first_body_inner(page: str) -> str:
    bodies = _doc_body_ranges(page)
    if not bodies:
        return ""
    start, close = bodies[0]
    return page[start:close]


def _replace_first_body_inner(page: str, inner: str) -> str:
    bodies = _doc_body_ranges(page)
    if not bodies:
        return page
    start, close = bodies[0]
    return page[:start] + inner + page[close:]


def _page_body_has_prose(page: str) -> bool:
    inner = _first_body_inner(page)
    if inner:
        return bool(_strip_tags(inner))
    stripped = re.sub(
        r"<footer\b[^>]*>.*?</footer>",
        "",
        page or "",
        flags=re.IGNORECASE | re.DOTALL,
    )
    return bool(_strip_tags(stripped))


def _has_cover_chrome(page: str) -> bool:
    if re.search(r"\bclass\s*=\s*[\"'][^\"']*\bdecision\b", page or "", re.IGNORECASE):
        return True
    return bool(
        re.search(
            r"data-slot\s*=\s*[\"']situation(?:-heading)?[\"']",
            page or "",
            re.IGNORECASE,
        )
    )


def _strip_page_breaks(fragment: str) -> str:
    return _PAGE_BREAK_RE.sub("\n", fragment or "")


def _trim_adjacent_page_breaks(prefix: str, suffix: str) -> tuple[str, str]:
    prefix = re.sub(
        r"(?:\s*<div\b[^>]*(?:data-nexus-page-break|class=[\"'][^\"']*\bpage-break)[^>]*>\s*</div>)+$",
        "\n",
        prefix or "",
        flags=re.IGNORECASE,
    )
    suffix = re.sub(
        r"^(?:\s*<div\b[^>]*(?:data-nexus-page-break|class=[\"'][^\"']*\bpage-break)[^>]*>\s*</div>)+",
        "\n",
        suffix or "",
        flags=re.IGNORECASE,
    )
    return prefix, suffix


def _drop_empty_pages(html: str) -> str:
    changed = True
    while changed:
        changed = False
        for start, end in _page_outer_ranges(html):
            if _page_body_has_prose(html[start:end]):
                continue
            prefix, suffix = _trim_adjacent_page_breaks(html[:start], html[end:])
            html = prefix + suffix
            changed = True
            break
    return html


def reflow_document(html: str) -> str:
    """Drop empty letter pages and remonter le texte after cover chrome delete."""
    if not html:
        return html
    html = _drop_empty_pages(html)
    pages = _page_outer_ranges(html)
    first = html[pages[0][0] : pages[0][1]] if len(pages) >= 2 else ""
    if len(pages) >= 2 and _first_body_inner(first) and not _has_cover_chrome(first):
        second = html[pages[1][0] : pages[1][1]]
        pulled = _first_body_inner(second)
        if pulled.strip():
            merged = _first_body_inner(first) + pulled
            first = _replace_first_body_inner(first, merged)
            html = html[: pages[0][0]] + first + html[pages[1][1] :]
            html = _drop_empty_pages(html)
    return html


def replace_class(html: str, class_name: str, replacement: str) -> str | dict[str, str]:
    """Replace the first element with ``class_name``. Empty deletes palette or decision."""
    token = (class_name or "").strip().lstrip(".")
    if not token or not re.fullmatch(r"[A-Za-z][\w-]{0,62}", token):
        return {"error": "class_name is required"}
    if not (replacement or "").strip() and token not in _DELETABLE_CLASSES:
        return {"error": _EMPTY_REPLACE_ERROR}
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


def insert_heading(
    html: str, title: str = "Heading", level: int = 2, after_heading: int = -1
) -> str:
    tag, cls = _INSERT_HEADING_STYLES[min(4, max(1, int(level or 2)))]
    return insert_after_heading_block(
        html,
        after_heading,
        f'<{tag} class="{cls}">{_escape(title or "Heading")}</{tag}>\n'
        f'<p class="fmz-normal"></p>',
    )


def insert_paragraph(html: str, text: str = "", after_heading: int = -1) -> str:
    return insert_after_heading_block(
        html, after_heading, f'<p class="fmz-normal">{_escape(text)}</p>'
    )


def insert_text(html: str, text: str, after_heading: int = -1) -> str:
    """Google Docs insertText analog: text becomes a paragraph in the HTML store."""
    return insert_paragraph(html, text, after_heading)


def insert_list(
    html: str,
    items: list[Any] | None = None,
    after_heading: int = -1,
    ordered: bool = False,
) -> str:
    tag = "ol" if ordered else "ul"
    inner = "".join(
        f"<li>{_escape(str(item))}</li>"
        for item in (items or [])
        if str(item or "").strip()
    )
    return insert_after_heading_block(html, after_heading, f"<{tag}>{inner}</{tag}>")


def insert_table(
    html: str,
    headers: list[Any] | None = None,
    rows: list[Any] | None = None,
    after_heading: int = -1,
    variant: str = "fmz-table",
) -> str:
    cls = variant if variant in {"fmz-table", "fmz-shaded"} else "fmz-table"
    ths = "".join(f"<th>{_escape(str(header))}</th>" for header in (headers or []))
    body: list[str] = []
    for row in rows or []:
        cells = row if isinstance(row, list) else [row]
        body.append(
            "<tr>"
            + "".join(f"<td>{_escape(str(cell))}</td>" for cell in cells)
            + "</tr>"
        )
    markup = (
        f'<table class="{cls}"><thead><tr>{ths}</tr></thead>'
        f"<tbody>{''.join(body)}</tbody></table>"
    )
    return insert_after_heading_block(html, after_heading, markup)


_ALLOWED_MARKS = frozenset({"strong", "em", "mark", "a"})


def apply_mark(
    html: str,
    find: str,
    mark: str = "strong",
    href: str = "",
    title: str = "",
) -> str | dict[str, str]:
    """Wrap the first find in strong, em, mark, or a link."""
    if not find:
        return {"error": "find is required"}
    needle = _escape(html_lib.unescape(find))
    kind = (mark or "strong").strip().lower()
    if kind not in _ALLOWED_MARKS:
        return {"error": f"Unknown mark {mark!r}. Use strong, em, mark, or a."}
    if kind == "a":
        target = (href or "").strip()
        if not target or urlsplit(target).scheme.lower() not in {
            "http",
            "https",
            "mailto",
        }:
            return {"error": "href must be an http, https, or mailto URL"}
        wrapped = f'<a href="{_attr(target)}">{needle}</a>'
    elif kind == "mark":
        comment = (title or "").strip()
        if comment:
            wrapped = (
                f'<mark class="fmz-comment" data-comment="{_attr(comment)}">'
                f"{needle}</mark>"
            )
        else:
            wrapped = f"<mark>{needle}</mark>"
    else:
        wrapped = f"<{kind}>{needle}</{kind}>"
    return replace_visible(html, find, wrapped, unique=True)


def insert_link(html: str, find: str, href: str) -> str | dict[str, str]:
    return apply_mark(html, find, mark="a", href=href)


def insert_image(
    html: str,
    src: str = "",
    alt: str = "",
    after_heading: int = -1,
) -> str | dict[str, str]:
    target = (src or "").strip()
    if not target or urlsplit(target).scheme.lower() not in {"http", "https"}:
        return {"error": "src must be an http or https URL"}
    markup = (
        f'<figure class="fmz-image"><img src="{_attr(target)}" '
        f'alt="{_attr(alt)}" /></figure>'
    )
    return insert_after_heading_block(html, after_heading, markup)


def insert_comment(html: str, find: str, text: str) -> str | dict[str, str]:
    note = (text or "").strip()
    if not note:
        return {"error": "text is required"}
    return apply_mark(html, find, mark="mark", title=note)


def insert_suggestion(html: str, find: str, replace: str) -> str | dict[str, str]:
    if not find:
        return {"error": "find is required"}
    if not (replace or "").strip():
        return {"error": "replace is required"}
    needle = _escape(html_lib.unescape(find))
    markup = (
        f'<del class="fmz-suggest-del">{needle}</del>'
        f'<ins class="fmz-suggest-ins">{_escape(replace)}</ins>'
    )
    return replace_visible(html, find, markup, unique=True)


def delete_block(
    html: str, class_name: str = "", slot: str = ""
) -> str | dict[str, str]:
    """Delete a block by class or data-slot. Situation removes the heading too."""
    slot = (slot or "").strip()
    class_name = (class_name or "").strip().lstrip(".")
    if slot:
        names = ["situation-heading", "situation"] if slot == "situation" else [slot]
        if slot == "decision":
            return replace_class(html, "decision", "")
        next_html = html
        found = False
        for name in names:
            span = _slot_span(next_html, name)
            if span is None:
                continue
            start, end = span
            next_html = next_html[:start] + next_html[end:]
            found = True
        if not found:
            return {"error": f"No slot {slot!r}"}
        return next_html
    if class_name:
        return replace_class(html, class_name, "")
    return {"error": "class_name or slot is required"}


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
    if not (replace or "").strip():
        return {"error": _EMPTY_REPLACE_ERROR}
    return replace_visible(html, find, _escape(replace), acknowledge=True)


_TITLE_SLOT_H1_RE = re.compile(
    r"(<h1\b[^>]*\bdata-slot\s*=\s*[\"']title[\"'][^>]*>).*?(</h1>)",
    re.IGNORECASE | re.DOTALL,
)


def update_document_title(html: str, title: str) -> str | dict[str, str]:
    """Set the tab ``<title>`` and the cover Title H1 to the same name.

    Prefers ``data-slot="title"``. Falls back to the first ``<h1>``.
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
    if _TITLE_SLOT_H1_RE.search(next_html):
        next_html = _TITLE_SLOT_H1_RE.sub(rf"\g<1>{safe}\g<2>", next_html, count=1)
        changed = True
    else:
        h1_open = _H1_OPEN_RE.search(next_html)
        if h1_open:
            next_html = _H1_FULL_RE.sub(
                f"{h1_open.group(0)}{safe}</h1>", next_html, count=1
            )
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


def _data_attrs(open_tag: str) -> str:
    attrs = [
        f"{match.group(1)}={match.group(2)}"
        for match in re.finditer(
            r'\s(data-[a-z0-9:-]+)\s*=\s*("[^"]*"|\'[^\']*\')',
            open_tag,
            re.IGNORECASE,
        )
    ]
    return (" " + " ".join(attrs)) if attrs else ""


def _style_class_attr(class_name: str) -> str:
    if class_name == "fmz-subtitle":
        return "fmz-subtitle subtitle"
    return class_name


def update_paragraph_style(
    html: str,
    heading_index: int | None = None,
    style: str = "",
    *,
    slot: str | None = None,
    class_name: str | None = None,
) -> str | dict[str, str]:
    spec = PARAGRAPH_STYLE_SPECS.get((style or "").strip().lower())
    if not spec:
        return {"error": (f"Unknown style {style!r}. Use {_PICKER_STYLE_NAMES}.")}
    tag, class_name_out = spec
    span: tuple[int, int] | None = None
    open_tag = ""
    inner = ""
    slot = (slot or "").strip() or None
    class_name = (class_name or "").strip().lstrip(".") or None
    if slot:
        span = _slot_span(html, slot)
        if span is None:
            return {"error": f"No slot {slot!r}"}
    elif class_name:
        span = _class_span(html, class_name)
        if span is None:
            return {"error": f"No element with class {class_name!r}"}
    if span is not None:
        start, end = span
        gt = html.find(">", start)
        open_tag = html[start : gt + 1] if gt >= 0 else ""
        close = (
            _matching_close_tag(
                html, open_tag[1:].split(None, 1)[0].rstrip(">"), gt + 1
            )
            if gt >= 0
            else None
        )
        if close is None:
            return {"error": "Unclosed element to style"}
        inner = html[gt + 1 : close]
        replacement = (
            f'<{tag} class="{_style_class_attr(class_name_out)}"'
            f"{_data_attrs(open_tag)}>{inner}</{tag}>"
        )
        return html[:start] + replacement + html[end:]
    matches = list(_HEADING_RE.finditer(html or ""))
    if not matches:
        return {"error": "No headings to style."}
    if heading_index is None or heading_index < 0 or heading_index >= len(matches):
        return {"error": f"heading_index out of range (0..{max(0, len(matches) - 1)})"}
    match = matches[heading_index]
    inner = match.group(2)
    open_end = match.group(0).find(">")
    open_tag = match.group(0)[: open_end + 1] if open_end >= 0 else ""
    replacement = (
        f'<{tag} class="{_style_class_attr(class_name_out)}"'
        f"{_data_attrs(open_tag)}>{inner}</{tag}>"
    )
    return html[: match.start()] + replacement + html[match.end() :]


def apply_document_commands(
    html: str, requests: list[dict[str, Any]]
) -> dict[str, Any]:
    """Apply an ordered list of document commands. Atomic: first error aborts."""
    if not isinstance(requests, list) or not requests:
        return {"error": "requests must be a non-empty list of command objects"}
    next_html = html
    fill_missing: list[str] = []
    applied: list[str] = []
    skipped: list[str] = []
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
        raw_index = raw.get("heading_index", max(after, 0))
        if raw_index is None:
            raw_index = max(after, 0)
        try:
            target = int(raw_index)
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
            heading_index = min(
                after + 1 if after >= 0 else len(outline) - 1, len(outline) - 1
            )
        elif typ == "insert_page_break":
            result = insert_page_break(next_html, after)
            heading_index = max(after, 0)
        elif typ == "insert_list":
            items = raw.get("items")
            if items is None and raw.get("text"):
                items = [raw.get("text")]
            if not isinstance(items, list):
                return {"error": f"requests[{i}].items must be an array"}
            result = insert_list(
                next_html, items, after, ordered=bool(raw.get("ordered"))
            )
            heading_index = max(after, 0)
        elif typ == "insert_table":
            headers = raw.get("headers") or []
            rows = raw.get("rows") or []
            if not isinstance(headers, list) or not isinstance(rows, list):
                return {"error": f"requests[{i}].headers and rows must be arrays"}
            result = insert_table(
                next_html,
                headers,
                rows,
                after,
                variant=str(raw.get("variant") or "fmz-table"),
            )
            heading_index = max(after, 0)
        elif typ == "insert_image":
            result = insert_image(
                next_html,
                src=str(raw.get("src") or raw.get("href") or ""),
                alt=str(raw.get("alt") or ""),
                after_heading=after,
            )
            heading_index = max(after, 0)
        elif typ == "apply_mark":
            result = apply_mark(
                next_html,
                find=str(raw.get("find") or raw.get("text") or ""),
                mark=str(raw.get("mark") or "strong"),
                href=str(raw.get("href") or ""),
                title=str(raw.get("title") or raw.get("comment") or ""),
            )
            heading_index = target
        elif typ == "insert_link":
            result = insert_link(
                next_html,
                find=str(raw.get("find") or raw.get("text") or ""),
                href=str(raw.get("href") or ""),
            )
            heading_index = target
        elif typ == "insert_comment":
            result = insert_comment(
                next_html,
                find=str(raw.get("find") or raw.get("text") or ""),
                text=str(
                    raw.get("comment") or raw.get("title") or raw.get("replace") or ""
                ),
            )
            heading_index = target
        elif typ == "insert_suggestion":
            result = insert_suggestion(
                next_html,
                find=str(raw.get("find") or ""),
                replace=str(raw.get("replace") or raw.get("text") or ""),
            )
            heading_index = target
        elif typ == "delete_range":
            result = delete_heading_range(next_html, target)
            if isinstance(result, str):
                heading_index = max(0, target - 1)
        elif typ == "delete_block":
            result = delete_block(
                next_html,
                class_name=str(raw.get("class_name") or ""),
                slot=str(raw.get("slot") or ""),
            )
            heading_index = target
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
            slot = str(raw.get("slot") or "").strip() or None
            class_name = str(raw.get("class_name") or "").strip() or None
            result = update_paragraph_style(
                next_html,
                None if (slot or class_name) else target,
                str(raw.get("style") or ""),
                slot=slot,
                class_name=class_name,
            )
            heading_index = target
        elif typ == "reflow":
            result = reflow_document(next_html)
            heading_index = 0
        elif typ in {"update_title", "rename_document"}:
            result = update_document_title(
                next_html, str(raw.get("title") or raw.get("text") or "")
            )
            heading_index = 0
        elif typ == "fill_slots":
            from naas_abi.tools.documents_slots import fill_document_slots

            filled = fill_document_slots(
                next_html, {k: v for k, v in raw.items() if k != "type"}
            )
            if filled.get("error"):
                return filled
            fill_missing.extend(filled.get("missing_slots", []))
            next_html = str(filled.get("html") or next_html)
            applied.append(typ)
            heading_index = 0
            continue
        else:
            return {"error": f"Unhandled command {typ!r}"}

        if isinstance(result, dict):
            err = str(result.get("error") or "")
            if typ in {"replace_text", "replace_class"} and err.startswith(
                ("Text not found", _EMPTY_REPLACE_ERROR)
            ):
                skipped.append(err)
                continue
            return result
        next_html = result
        applied.append(typ)

    if not applied:
        leftover = leftover_write_note(html)
        if leftover.get("leftover_slots"):
            extra = leftover.get("warning") or (
                "leftover_slots remain. Call fill_document_slots once "
                "with those keys, then stop."
            )
        else:
            extra = (
                "Stop and reply. Do not apply again. leftover_slots is empty, "
                "so do not call fill_document_slots."
            )
        return {
            "error": (
                "No commands applied. apply_document_commands is not the "
                "fill path. " + extra
            ),
            "skipped": skipped,
            **leftover,
        }

    next_html = normalize_document_flow(next_html)
    outline = heading_outline(next_html)
    if heading_index >= len(outline):
        heading_index = max(0, len(outline) - 1)
    unfilled = [
        field["name"] for field in template_fields(next_html) if field["unfilled"]
    ]
    completeness = {
        "missing_slots": list(dict.fromkeys([*fill_missing, *unfilled])),
        "content_complete": not fill_missing
        and not unfilled
        and not leftover_placeholders(next_html),
    }
    if unfilled:
        completeness["incomplete"] = True
    return {
        "ok": True,
        "html": next_html,
        "applied": applied,
        "skipped": skipped,
        "outline": outline,
        "heading_index": heading_index,
        "heading_count": len(outline),
        "section_index": heading_index,
        "section_count": len(outline),
        "ids": [None] * len(outline),
        "sections": outline,
        **leftover_write_note(next_html),
        **completeness,
    }
