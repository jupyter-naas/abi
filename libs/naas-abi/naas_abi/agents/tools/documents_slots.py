"""Deterministic slot fill for Portrait A4 (and the same letter-page seed).

The model sends structured topic copy. Python maps it onto the open HTML.
No exact seed-string find. Empty values are rejected. Unknown keys ignored.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

from naas_abi.agents.tools.documents_commands import (
    leftover_placeholders,
    leftover_slots,
    leftover_write_note,
    normalize_document_flow,
    replace_class,
    update_document_title,
)

_SLOT_OPEN_RE = re.compile(
    r"<(?P<tag>[a-z][a-z0-9]*)\b[^>]*\bdata-slot\s*=\s*[\"'](?P<slot>[^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)
_CLASS_OPEN_RE = re.compile(
    r"<(?P<tag>[a-z][a-z0-9]*)\b[^>]*\bclass\s*=\s*[\"'][^\"']*\b(?P<cls>subtitle|intro|note|palette|fm-table|fm-shaded)\b[^\"']*[\"'][^>]*>",
    re.IGNORECASE,
)
_LAYOUT_OPEN_RE = re.compile(
    r"<section\b[^>]*\bdata-layout\s*=\s*[\"'](?P<layout>[^\"']+)[\"'][^>]*>",
    re.IGNORECASE,
)
_HEADING_OPEN_RE = re.compile(r"<h([1-4])\b[^>]*>", re.IGNORECASE)
_P_OPEN_RE = re.compile(r"<p\b[^>]*>", re.IGNORECASE)
_UL_OPEN_RE = re.compile(r"<ul\b[^>]*>", re.IGNORECASE)
_QUOTE_OPEN_RE = re.compile(r"<blockquote\b[^>]*>", re.IGNORECASE)
_TABLE_OPEN_RE = re.compile(r"<table\b[^>]*>", re.IGNORECASE)
_VOID_TAGS = frozenset({"area", "base", "br", "col", "embed", "hr", "img", "input", "link", "meta"})

REQUIRED_KEYS = (
    "title",
    "subtitle",
    "intro",
    "note",
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
    tag = open_match.group("tag") if "tag" in open_match.re.groupindex else open_match.group(0)
    if tag.startswith("<"):
        tag_m = re.match(r"<([a-z][a-z0-9]*)", tag, re.I)
        tag = tag_m.group(1) if tag_m else ""
    if not tag:
        return None
    close = _matching_close(html, tag, open_match.end())
    if close is None:
        return None
    return f"{html[:open_match.end()]}{_escape(text)}{html[close:]}"


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
        close = _matching_close(html, "section", match.end())
        if close is not None:
            return match.end(), close
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
    return f"{html[:open_match.end()]}{inner}{html[close:]}"


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


def _fill_cover(html: str, payload: dict[str, Any]) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    title = _require_text(payload["title"] if "title" in payload else None, "title")
    if isinstance(title, dict):
        return html, filled, missing, title
    if title:
        updated = update_document_title(html, title)
        if isinstance(updated, str):
            html = updated
            filled.append("title")
        else:
            return html, filled, missing, updated
    else:
        missing.append("title")

    for key in ("subtitle", "intro", "note"):
        value = _require_text(payload[key] if key in payload else None, key)
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
    return html, filled, missing, None


def _fill_quote(html: str, payload: dict[str, Any]) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    quote = _require_text(payload["quote"] if "quote" in payload else None, "quote")
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
                updated = _replace_open_inner(html, open_m, "blockquote", _escape(quote))
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
        missing.append("sections")
        return html, filled, missing, None
    sections = payload.get("sections")
    if not isinstance(sections, list) or not sections:
        return html, filled, missing, {"error": "sections must be a non-empty array"}
    span = _layout_range(html, "content")
    if span is None:
        missing.append("sections")
        return html, filled, missing, None
    start, end = span
    for i, raw in enumerate(sections):
        if not isinstance(raw, dict):
            return html, filled, missing, {"error": f"sections[{i}] must be an object"}
        heading = _require_text(raw["heading"] if "heading" in raw else None, f"sections[{i}].heading")
        body = _require_text(raw["body"] if "body" in raw else None, f"sections[{i}].body")
        if isinstance(heading, dict):
            return html, filled, missing, heading
        if isinstance(body, dict):
            return html, filled, missing, body
        bullets = raw.get("bullets")
        if bullets is not None and not isinstance(bullets, list):
            return html, filled, missing, {"error": f"sections[{i}].bullets must be an array"}
        if bullets is not None:
            for j, item in enumerate(bullets):
                if not str(item or "").strip():
                    return html, filled, missing, {
                        "error": f"sections[{i}].bullets[{j}] must be a non-empty topic sentence"
                    }
        slot_h = f"section-{i}"
        if heading:
            updated = _set_slot(html, slot_h, heading)
            if updated is None:
                open_m = _nth_open_in_range(html, _HEADING_OPEN_RE, start, end, i)
                if open_m:
                    updated = _replace_open_inner(
                        html, open_m, f"h{open_m.group(1)}", _escape(heading)
                    )
            if updated is None:
                missing.append(f"sections[{i}].heading")
            else:
                html = updated
                filled.append(f"sections[{i}].heading")
                span = _layout_range(html, "content") or span
                start, end = span
        else:
            missing.append(f"sections[{i}].heading")
        if body:
            updated = _set_slot(html, f"section-{i}-body", body)
            if updated is None:
                open_m = _nth_open_in_range(html, _P_OPEN_RE, start, end, i)
                if open_m:
                    updated = _replace_open_inner(html, open_m, "p", _escape(body))
            if updated is None:
                missing.append(f"sections[{i}].body")
            else:
                html = updated
                filled.append(f"sections[{i}].body")
                span = _layout_range(html, "content") or span
                start, end = span
        else:
            missing.append(f"sections[{i}].body")
        if bullets:
            items = _list_items_html(bullets)
            updated = _set_slot(html, f"section-{i}-list", "")  # probe
            list_updated = None
            slot_m = None
            for match in _SLOT_OPEN_RE.finditer(html):
                if match.group("slot") == f"section-{i}-list":
                    slot_m = match
                    break
            if slot_m:
                list_updated = _replace_open_inner(html, slot_m, slot_m.group("tag"), items)
            else:
                open_m = _nth_open_in_range(html, _UL_OPEN_RE, start, end, 0 if i == 0 else i)
                if open_m:
                    list_updated = _replace_open_inner(html, open_m, "ul", items)
            if list_updated:
                html = list_updated
                filled.append(f"sections[{i}].bullets")
                span = _layout_range(html, "content") or span
                start, end = span
    return html, filled, missing, None


def _fill_tables(
    html: str, payload: dict[str, Any]
) -> tuple[str, list[str], list[str], dict[str, str] | None]:
    filled: list[str] = []
    missing: list[str] = []
    heading = _require_text(
        payload["tables_heading"] if "tables_heading" in payload else None,
        "tables_heading",
    )
    intro = _require_text(
        payload["tables_intro"] if "tables_intro" in payload else None,
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
        th = _require_text(raw["heading"] if "heading" in raw else None, f"tables[{i}].heading")
        if isinstance(th, dict):
            return html, filled, missing, th
        headers = raw.get("headers")
        rows = raw.get("rows")
        if headers is not None and (
            not isinstance(headers, list)
            or not headers
            or any(not str(h or "").strip() for h in headers)
        ):
            return html, filled, missing, {
                "error": f"tables[{i}].headers must be non-empty topic labels"
            }
        if rows is not None and (
            not isinstance(rows, list)
            or not rows
            or any(not isinstance(row, list) or not row for row in rows)
        ):
            return html, filled, missing, {
                "error": f"tables[{i}].rows must be a non-empty array of row arrays"
            }
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
                    updated = _replace_open_inner(html, match, match.group("tag"), inner)
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


def fill_document_slots(html: str, payload: dict[str, Any]) -> dict[str, Any]:
    """Map structured topic copy onto the open template. Footer stays put."""
    if not isinstance(payload, dict):
        return {"error": "slots must be an object"}
    next_html = html or ""
    filled: list[str] = []
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

    next_html = normalize_document_flow(next_html)
    note = leftover_write_note(next_html)
    leftovers = leftover_placeholders(next_html)
    incomplete = bool(missing or leftovers)
    warning = ""
    if incomplete:
        warning = (
            "INCOMPLETE: missing_slots="
            + ", ".join(missing)
            + ("; leftover_placeholders=" + ", ".join(leftovers) if leftovers else "")
            + ". Call fill_document_slots once more with only the missing slots. "
            "Each value must be a non-empty topic sentence. "
            "Do not write the memo only in chat."
        )
    return {
        "ok": True,
        "html": next_html,
        "filled": filled,
        "missing_slots": missing,
        "leftover_placeholders": leftovers,
        "leftover_slots": leftover_slots(next_html),
        "incomplete": incomplete,
        "warning": warning,
        **{k: v for k, v in note.items() if k not in {"leftover_placeholders", "leftover_slots", "incomplete", "warning"}},
    }
