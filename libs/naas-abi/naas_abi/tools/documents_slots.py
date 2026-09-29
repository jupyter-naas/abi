"""Deterministic slot fill for Portrait A4 (and the same letter-page seed).

The model sends structured topic copy. Python maps it onto the open HTML.
No exact seed-string find. Empty values are rejected. Unknown keys ignored.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

from naas_abi.tools.documents_commands import (
    delete_block,
    heading_outline,
    leftover_placeholders,
    leftover_slots,
    leftover_write_note,
    normalize_document_flow,
    replace_class,
    update_document_title,
)
from naas_abi.tools.documents_html import (
    DocumentHTML,
    acknowledge_filled_fields,
    template_fields,
)

_SLOT_OPEN_RE = re.compile(
    r"<(?P<tag>[a-z][a-z0-9]*)\b[^>]*\bdata-slot\s*=\s*[\"'](?P<slot>[^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)
_TITLE_SLOT_OPEN_RE = re.compile(
    r"<(?P<tag>[a-z][a-z0-9]*)\b(?P<attrs>[^>]*\bdata-slot\s*=\s*[\"']title[\"'][^>]*)>",
    re.IGNORECASE,
)
_CLASS_OPEN_RE = re.compile(
    r"<(?P<tag>[a-z][a-z0-9]*)\b[^>]*\bclass\s*=\s*[\"'][^\"']*\b(?P<cls>subtitle|intro|note|palette|fmz-table|fmz-shaded|fm-table|fm-shaded)\b[^\"']*[\"'][^>]*>",
    re.IGNORECASE,
)
_LAYOUT_OPEN_RE = re.compile(
    r"<(?P<tag>section|div)\b[^>]*\bdata-layout\s*=\s*[\"'](?P<layout>[^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)
_HEADING_OPEN_RE = re.compile(r"<h([1-4])\b[^>]*>", re.IGNORECASE)
_P_OPEN_RE = re.compile(r"<p\b[^>]*>", re.IGNORECASE)
_UL_OPEN_RE = re.compile(r"<ul\b[^>]*>", re.IGNORECASE)
_QUOTE_OPEN_RE = re.compile(r"<blockquote\b[^>]*>", re.IGNORECASE)
_TABLE_OPEN_RE = re.compile(r"<table\b[^>]*>", re.IGNORECASE)
_VOID_TAGS = frozenset(
    {"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"}
)

REQUIRED_KEYS = (
    "title",
    "subtitle",
    "intro",
    "quote",
    "sections",
    "tables_heading",
    "tables_intro",
    "tables",
)


def _escape(text: str) -> str:
    return html_lib.escape(text or "", quote=False)


def _matching_close(html: str, tag: str, inner_start: int) -> int | None:
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


def _set_inner(html: str, open_match: re.Match[str], text: str) -> str | None:
    tag = (
        open_match.group("tag")
        if "tag" in open_match.re.groupindex
        else open_match.group(0)
    )
    if tag.startswith("<"):
        tag_m = re.match(r"<([a-z][a-z0-9]*)", tag, re.IGNORECASE)
        tag = tag_m.group(1) if tag_m else ""
    if not tag:
        return None
    close = _matching_close(html, tag, open_match.end())
    if close is None:
        return None
    return f"{html[: open_match.end()]}{_escape(text)}{html[close:]}"


def ensure_title_slot_is_h1(html: str) -> str:
    """Cover Title is an H1. Promote ``data-slot="title"`` if it landed on H2+."""
    match = _TITLE_SLOT_OPEN_RE.search(html or "")
    if not match:
        return html
    tag = match.group("tag")
    close = _matching_close(html, tag, match.end())
    if close is None:
        return html
    close_m = re.match(rf"</{re.escape(tag)}\s*>", html[close:], re.IGNORECASE)
    end = close + (close_m.end() if close_m else 0)
    inner = html[match.end() : close]
    attrs = re.sub(
        r"\sclass\s*=\s*[\"'][^\"']*[\"']",
        "",
        match.group("attrs") or "",
        flags=re.IGNORECASE,
    )
    new_open = f'<h1 class="fmz-title"{attrs}>'
    return f"{html[: match.start()]}{new_open}{inner}</h1>{html[end:]}"


def _set_slot(html: str, slot: str, text: str) -> str | None:
    for match in _SLOT_OPEN_RE.finditer(html):
        if match.group("slot") == slot:
            return _set_inner(html, match, text)
    return None


def _set_class_inner(html: str, class_name: str, text: str) -> str | None:
    for match in _CLASS_OPEN_RE.finditer(html):
        if match.group("cls").lower() == class_name.lower():
            return _set_inner(html, match, text)
    return None


def _layout_range(html: str, layout: str) -> tuple[int, int] | None:
    for match in _LAYOUT_OPEN_RE.finditer(html):
        if match.group("layout").lower() != layout.lower():
            continue
        tag = match.group("tag")
        close = _matching_close(html, tag, match.end())
        if close is not None:
            for node in DocumentHTML(html).elements:
                if (
                    node.start >= match.end()
                    and node.end <= close
                    and "doc-body" in str(node.attrs.get("class", "")).split()
                ):
                    return node.inner, node.close
            return match.end(), close
    return None


def _is_impl_heading(open_tag: str) -> bool:
    return bool(re.search(r"data-slot\s*=\s*[\"']impl-", open_tag or "", re.IGNORECASE))


def _nth_section_heading_in_range(
    html: str, start: int, end: int, index: int
) -> re.Match[str] | None:
    found = 0
    for match in _HEADING_OPEN_RE.finditer(html):
        if match.start() < start or match.start() >= end:
            continue
        if _is_impl_heading(match.group(0)):
            continue
        if found == index:
            return match
        found += 1
    return None


def _nth_open_in_range(
    html: str, pattern: re.Pattern[str], start: int, end: int, index: int
) -> re.Match[str] | None:
    found = 0
    for match in pattern.finditer(html):
        if match.start() < start or match.start() >= end:
            continue
        if found == index:
            return match
        found += 1
    return None


def _replace_open_inner(
    html: str, open_match: re.Match[str], tag: str, inner: str
) -> str | None:
    close = _matching_close(html, tag, open_match.end())
    if close is None:
        return None
    return f"{html[: open_match.end()]}{inner}{html[close:]}"


def _require_text(value: Any, label: str) -> str | dict[str, str]:
    if value is None:
        return ""
    text = str(value).strip()
    if value != "" and not text:
        return {"error": f"{label} must be a non-empty topic sentence"}
    return text


def _list_items_html(items: list[Any]) -> str:
    lines = []
    for item in items:
        text = str(item or "").strip()
        if text:
            lines.append(f"<li>{_escape(text)}</li>")
    return "".join(lines)


def _table_inner(headers: list[Any], rows: list[Any]) -> str:
    ths = "".join(f"<th>{_escape(str(h))}</th>" for h in headers)
    body = []
    for row in rows:
        cells = row if isinstance(row, list) else [row]
        tds = "".join(f"<td>{_escape(str(c))}</td>" for c in cells)
        body.append(f"<tr>{tds}</tr>")
    return f"<thead><tr>{ths}</tr></thead><tbody>{''.join(body)}</tbody>"


def _fill_cover(
    html: str, payload: dict[str, Any]
) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    title = _require_text(payload.get("title"), "title")
    if isinstance(title, dict):
        return html, filled, missing, title
    if title:
        html = ensure_title_slot_is_h1(html)
        slotted = _set_slot(html, "title", title)
        if slotted is not None:
            html = slotted
        updated = update_document_title(html, title)
        if isinstance(updated, str):
            html = updated
            filled.append("title")
        else:
            return html, filled, missing, updated
    else:
        missing.append("title")

    for key in ("subtitle", "intro"):
        value = _require_text(payload.get(key), key)
        if isinstance(value, dict):
            return html, filled, missing, value
        if not value:
            missing.append(key)
            continue
        updated = _set_slot(html, key, value) or _set_class_inner(html, key, value)
        if updated is None:
            missing.append(key)
            continue
        html = updated
        filled.append(key)

    if "situation" in payload:
        situation = _require_text(payload.get("situation"), "situation")
        if isinstance(situation, dict):
            return html, filled, missing, situation
        if situation:
            updated = _set_slot(html, "situation", situation)
            if updated is None:
                missing.append("situation")
            else:
                html = updated
                filled.append("situation")
            heading = _require_text(
                payload.get("situation-heading"),
                "situation-heading",
            )
            if isinstance(heading, dict):
                return html, filled, missing, heading
            if heading:
                headed = _set_slot(html, "situation-heading", heading)
                if headed is not None:
                    html = headed
                    filled.append("situation-heading")
        else:
            deleted = delete_block(html, slot="situation")
            if isinstance(deleted, str):
                html = deleted
                filled.append("situation")

    if "note" in payload:
        note = _require_text(payload.get("note"), "note")
        if isinstance(note, dict):
            return html, filled, missing, note
        if note:
            updated = _set_slot(html, "note", note) or _set_class_inner(
                html, "note", note
            )
            if updated is None:
                missing.append("note")
            else:
                html = updated
                filled.append("note")
        else:
            deleted = replace_class(html, "decision", "")
            if isinstance(deleted, str):
                html = deleted
                filled.append("note")
    else:
        deleted = replace_class(html, "decision", "")
        if isinstance(deleted, str):
            html = deleted
        elif (
            _set_slot(html, "note", "x") is not None
            or _set_class_inner(html, "note", "x") is not None
        ):
            missing.append("note")
    return html, filled, missing, None


def _fill_quote(
    html: str, payload: dict[str, Any]
) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    quote = _require_text(payload.get("quote"), "quote")
    if isinstance(quote, dict):
        return html, filled, missing, quote
    if not quote:
        missing.append("quote")
        return html, filled, missing, None
    updated = _set_slot(html, "quote", quote)
    if updated is None:
        span = _layout_range(html, "content")
        if span:
            open_m = _nth_open_in_range(html, _QUOTE_OPEN_RE, span[0], span[1], 0)
            if open_m:
                updated = _replace_open_inner(
                    html, open_m, "blockquote", _escape(quote)
                )
    if updated is None:
        missing.append("quote")
        return html, filled, missing, None
    return updated, ["quote"], missing, None


def _fill_sections(
    html: str, payload: dict[str, Any]
) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    if "sections" not in payload:
        return html, filled, ["sections"], None
    sections = payload["sections"]
    if not isinstance(sections, list) or not sections:
        return html, filled, missing, {"error": "sections must be a non-empty array"}
    slotted = bool(re.search(r'data-slot=["\']section-\d+["\']', html))
    for i, raw in enumerate(sections):
        if not isinstance(raw, dict):
            return html, filled, missing, {"error": f"sections[{i}] must be an object"}
        heading = _require_text(raw.get("heading"), f"sections[{i}].heading")
        body = _require_text(raw.get("body"), f"sections[{i}].body")
        if isinstance(heading, dict) or isinstance(body, dict):
            return html, filled, missing, heading if isinstance(heading, dict) else body
        bullets = raw.get("bullets")
        if bullets is not None and (
            not isinstance(bullets, list)
            or any(not isinstance(item, str) or not item.strip() for item in bullets)
        ):
            return (
                html,
                filled,
                missing,
                {
                    "error": f"sections[{i}].bullets must be an array of non-empty strings"
                },
            )
        span = _layout_range(html, "content")
        if span is None:
            return html, filled, ["sections"], None
        parsed = DocumentHTML(html)
        target = parsed.fields().get(f"section-{i}")
        if target is None and not slotted:
            headings = [
                n
                for n in parsed.elements
                if n.tag in {"h2", "h3", "h4"} and span[0] <= n.start < span[1]
            ]
            target = headings[i] if i < len(headings) else None
        if target is None:
            if not heading:
                missing.append(f"sections[{i}].heading")
                continue
            markup = f'<h2 class="fmz-heading-1" data-slot="section-{i}">{_escape(heading)}</h2>'
            html = html[: span[1]] + markup + html[span[1] :]
            target = DocumentHTML(html).fields()[f"section-{i}"]
        elif heading:
            html = html[: target.inner] + _escape(heading) + html[target.close :]
        if heading:
            filled.append(f"sections[{i}].heading")
        else:
            missing.append(f"sections[{i}].heading")
        # Reparse after each edit, keeping exact source ranges valid.
        parsed = DocumentHTML(html)
        target = next(n for n in parsed.elements if n.start == target.start)
        span = _layout_range(html, "content")
        boundary = next(
            (
                n.start
                for n in parsed.elements
                if n.tag in {"h2", "h3", "h4"}
                and n.start > target.start
                and n.start < span[1]
            ),
            span[1],
        )
        body_node = parsed.fields().get(f"section-{i}-body")
        if body_node is None and not slotted:
            body_node = next(
                (
                    n
                    for n in parsed.elements
                    if n.tag == "p" and target.end <= n.start < boundary
                ),
                None,
            )
        if body:
            if body_node:
                html = html[: body_node.inner] + _escape(body) + html[body_node.close :]
            else:
                markup = f'<p class="fmz-normal" data-slot="section-{i}-body">{_escape(body)}</p>'
                html = html[: target.end] + markup + html[target.end :]
            filled.append(f"sections[{i}].body")
        else:
            missing.append(f"sections[{i}].body")
        if bullets is not None:
            parsed = DocumentHTML(html)
            node = parsed.fields().get(f"section-{i}-list")
            if node:
                html = (
                    html[: node.inner] + _list_items_html(bullets) + html[node.close :]
                )
            else:
                body_node = parsed.fields().get(f"section-{i}-body")
                at = (
                    body_node.end
                    if body_node
                    else next(n.end for n in parsed.elements if n.start == target.start)
                )
                markup = (
                    f'<ul data-slot="section-{i}-list">{_list_items_html(bullets)}</ul>'
                )
                html = html[:at] + markup + html[at:]
            filled.append(f"sections[{i}].bullets")
    return html, filled, missing, None


def _fill_tables(
    html: str, payload: dict[str, Any]
) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    heading = _require_text(
        payload.get("tables_heading"),
        "tables_heading",
    )
    intro = _require_text(
        payload.get("tables_intro"),
        "tables_intro",
    )
    if isinstance(heading, dict):
        return html, filled, missing, heading
    if isinstance(intro, dict):
        return html, filled, missing, intro
    span = _layout_range(html, "tables")
    if span is None:
        if "tables" in payload or heading or intro:
            missing.append("tables")
        return html, filled, missing, None
    start, end = span
    if heading:
        updated = _set_slot(html, "tables-heading", heading)
        if updated is None:
            open_m = _nth_open_in_range(html, _HEADING_OPEN_RE, start, end, 0)
            if open_m:
                updated = _replace_open_inner(
                    html, open_m, f"h{open_m.group(1)}", _escape(heading)
                )
        if updated:
            html = updated
            filled.append("tables_heading")
            span = _layout_range(html, "tables") or span
            start, end = span
        else:
            missing.append("tables_heading")
    else:
        missing.append("tables_heading")
    if intro:
        updated = _set_slot(html, "tables-intro", intro)
        if updated is None:
            open_m = _nth_open_in_range(html, _P_OPEN_RE, start, end, 0)
            if open_m:
                updated = _replace_open_inner(html, open_m, "p", _escape(intro))
        if updated:
            html = updated
            filled.append("tables_intro")
            span = _layout_range(html, "tables") or span
            start, end = span
        else:
            missing.append("tables_intro")
    else:
        missing.append("tables_intro")

    if "tables" not in payload:
        missing.append("tables")
        return html, filled, missing, None
    tables = payload.get("tables")
    if not isinstance(tables, list) or not tables:
        return html, filled, missing, {"error": "tables must be a non-empty array"}
    for i, raw in enumerate(tables):
        if not isinstance(raw, dict):
            return html, filled, missing, {"error": f"tables[{i}] must be an object"}
        th = _require_text(raw.get("heading"), f"tables[{i}].heading")
        if isinstance(th, dict):
            return html, filled, missing, th
        headers = raw.get("headers")
        rows = raw.get("rows")
        if headers is not None and (
            not isinstance(headers, list)
            or not headers
            or any(not str(h or "").strip() for h in headers)
        ):
            return (
                html,
                filled,
                missing,
                {"error": f"tables[{i}].headers must be non-empty topic labels"},
            )
        if rows is not None and (
            not isinstance(rows, list)
            or not rows
            or any(not isinstance(row, list) or not row for row in rows)
        ):
            return (
                html,
                filled,
                missing,
                {"error": f"tables[{i}].rows must be a non-empty array of row arrays"},
            )
        if th:
            updated = _set_slot(html, f"table-{i}-heading", th)
            if updated is None:
                open_m = _nth_open_in_range(html, _HEADING_OPEN_RE, start, end, i + 1)
                if open_m:
                    updated = _replace_open_inner(
                        html, open_m, f"h{open_m.group(1)}", _escape(th)
                    )
            if updated:
                html = updated
                filled.append(f"tables[{i}].heading")
                span = _layout_range(html, "tables") or span
                start, end = span
            else:
                missing.append(f"tables[{i}].heading")
        else:
            missing.append(f"tables[{i}].heading")
        if headers and rows:
            inner = _table_inner(headers, rows)
            updated = None
            for match in _SLOT_OPEN_RE.finditer(html):
                if match.group("slot") == f"table-{i}":
                    updated = _replace_open_inner(
                        html, match, match.group("tag"), inner
                    )
                    break
            if updated is None:
                open_m = _nth_open_in_range(html, _TABLE_OPEN_RE, start, end, i)
                if open_m:
                    updated = _replace_open_inner(html, open_m, "table", inner)
            if updated:
                html = updated
                filled.append(f"tables[{i}]")
                span = _layout_range(html, "tables") or span
                start, end = span
            else:
                missing.append(f"tables[{i}]")
        else:
            if "headers" not in raw or "rows" not in raw:
                missing.append(f"tables[{i}]")
    return html, filled, missing, None


_GENERIC_KEYS = set(REQUIRED_KEYS) | {
    "note",
    "situation",
    "situation-heading",
    "keep_palette",
    "fields",
}


def _prepare_base_blocks(source: str, payload: dict[str, Any]) -> str:
    """Provision missing regions inside the body of blank/legacy templates."""
    parsed = DocumentHTML(source)
    body = next(
        (
            n
            for n in parsed.elements
            if "doc-body" in str(n.attrs.get("class", "")).split() and n.close >= 0
        ),
        None,
    )
    if body is None:
        return source
    additions = []
    if payload.get("sections") and _layout_range(source, "content") is None:
        additions.append('<div class="doc-region" data-layout="content"></div>')
    if payload.get("tables") and _layout_range(source, "tables") is None:
        additions.append(
            '<div class="doc-region" data-layout="tables"><h2 data-slot="tables-heading"></h2><p data-slot="tables-intro"></p></div>'
        )
    source = source[: body.close] + "".join(additions) + source[body.close :]
    # Quote/note are optional blocks, created only when requested.
    for key, tag in (("quote", "blockquote"), ("note", "p")):
        if (
            payload.get(key)
            and _set_slot(source, key, "probe") is None
            and _set_class_inner(source, key, "probe") is None
            and not (key == "quote" and _QUOTE_OPEN_RE.search(source))
        ):
            body = next(
                n
                for n in DocumentHTML(source).elements
                if "doc-body" in str(n.attrs.get("class", "")).split() and n.close >= 0
            )
            source = (
                source[: body.close]
                + f'<{tag} data-slot="{key}"></{tag}>'
                + source[body.close :]
            )
    # Tables can be repeated beyond the seed's initial examples.
    tables = payload.get("tables")
    if isinstance(tables, list):
        for i, _ in enumerate(tables):
            fields = DocumentHTML(source).fields()
            if f"table-{i}" not in fields:
                span = _layout_range(source, "tables")
                if span:
                    markup = f'<h3 data-slot="table-{i}-heading"></h3><table class="fmz-table" data-slot="table-{i}"></table>'
                    source = source[: span[1]] + markup + source[span[1] :]
    return source


def _fill_fields(
    source: str, payload: dict[str, Any]
) -> tuple[str, list[str], dict | None]:
    fields = payload.get("fields", {})
    if not isinstance(fields, dict):
        return (
            source,
            [],
            {"error": "fields must be an object keyed by template field name"},
        )
    values = {**{k: v for k, v in payload.items() if k not in _GENERIC_KEYS}, **fields}
    filled = []
    for name, value in values.items():
        nodes = DocumentHTML(source).fields()
        node = nodes.get(name)
        if node is None:
            return (
                source,
                [],
                {
                    "error": f"Unknown template field: {name}",
                    "available_fields": list(nodes),
                },
            )
        if node.tag in {"ul", "ol"}:
            if not isinstance(value, list) or any(
                not isinstance(v, str) or not v.strip() for v in value
            ):
                return (
                    source,
                    [],
                    {"error": f"{name} must be an array of non-empty strings"},
                )
            markup = _list_items_html(value)
        elif node.tag == "table":
            if (
                not isinstance(value, dict)
                or not isinstance(value.get("headers"), list)
                or not isinstance(value.get("rows"), list)
            ):
                return (
                    source,
                    [],
                    {"error": f"{name} must contain headers and rows arrays"},
                )
            headers, rows = value["headers"], value["rows"]
            if not headers or any(
                not isinstance(row, list) or len(row) != len(headers) for row in rows
            ):
                return source, [], {"error": f"{name} rows must match the header count"}
            markup = _table_inner(headers, rows)
        else:
            if not isinstance(value, str) or not value.strip():
                return source, [], {"error": f"{name} must be non-empty text"}
            markup = _escape(value)
        source = source[: node.inner] + markup + source[node.close :]
        filled.append(name)
    return source, filled, None


def fill_document_slots(html: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Map structured topic copy onto the open template. Footer stays put."""
    if not isinstance(payload, dict):
        return {"error": "slots must be an object"}
    next_html = _prepare_base_blocks(html or "", payload)
    next_html, custom_filled, field_error = _fill_fields(next_html, payload)
    if field_error:
        return field_error
    filled: list[str] = list(custom_filled)
    missing: list[str] = []

    next_html, got, miss, err = _fill_cover(next_html, payload)
    if err:
        return err
    filled.extend(got)
    missing.extend(miss)

    if not payload.get("keep_palette"):
        updated = replace_class(next_html, "palette", "")
        if isinstance(updated, str):
            next_html = updated
            filled.append("palette")

    next_html, got, miss, err = _fill_quote(next_html, payload)
    if err:
        return err
    filled.extend(got)
    missing.extend(miss)

    next_html, got, miss, err = _fill_sections(next_html, payload)
    if err:
        return err
    filled.extend(got)
    missing.extend(miss)

    next_html, got, miss, err = _fill_tables(next_html, payload)
    if err:
        return err
    filled.extend(got)
    missing.extend(miss)

    if not filled:
        return {
            "error": (
                "No slots filled. Send title, subtitle, intro, note, quote, "
                "sections, tables_heading, tables_intro, and tables."
            ),
            "missing_slots": missing,
        }

    next_html = acknowledge_filled_fields(next_html, filled)
    next_html = normalize_document_flow(next_html)
    outline = heading_outline(next_html)
    note = leftover_write_note(next_html)
    leftovers = leftover_placeholders(next_html)
    for field in template_fields(next_html):
        if field["unfilled"]:
            missing.append(field["name"])
    missing = list(dict.fromkeys(missing))
    incomplete = bool(missing or leftovers)
    warning = ""
    if missing:
        warning = (
            "missing_slots="
            + ", ".join(missing)
            + ("; leftover_placeholders=" + ", ".join(leftovers) if leftovers else "")
            + ". Stop and reply. Do not call fill_document_slots again this turn. "
            "missing_slots wait for a later turn. "
            "Do not write the memo only in chat."
        )
    elif leftovers:
        warning = leftover_write_note(next_html).get("warning") or (
            "leftover_placeholders="
            + ", ".join(leftovers)
            + ". Stop and reply. Do not call fill_document_slots again this turn."
        )
    return {
        "ok": True,
        "content_complete": not incomplete,
        "html": next_html,
        "section_index": 0,
        "section_count": len(outline),
        "ids": [None] * len(outline),
        "filled": filled,
        "missing_slots": missing,
        "leftover_placeholders": leftovers,
        "leftover_slots": leftover_slots(next_html),
        "incomplete": incomplete,
        "warning": warning,
        **{
            k: v
            for k, v in note.items()
            if k
            not in {"leftover_placeholders", "leftover_slots", "incomplete", "warning"}
        },
    }
