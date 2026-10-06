"""Source-preserving HTML ranges for document content and template fields.

Uses the standard parser; mutations never serialize or rewrite styles/assets.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from html.parser import HTMLParser

_VOID = {
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
_PROTECTED = {"head", "script", "style", "svg", "footer", "header"}


@dataclass
class Element:
    tag: str
    attrs: dict[str, str | None]
    start: int
    inner: int
    close: int = -1
    end: int = -1
    protected: bool = False


class DocumentHTML(HTMLParser):
    def __init__(self, source: str):
        super().__init__(convert_charrefs=False)
        self.source = source
        self.offsets = [0]
        self.offsets.extend(m.end() for m in re.finditer("\n", source))
        self.elements: list[Element] = []
        self.stack: list[Element] = []
        self.text_ranges: list[tuple[int, int]] = []
        self.feed(source)
        self.close()

    def source_offset(self) -> int:
        line, col = self.getpos()
        return self.offsets[line - 1] + col

    def handle_starttag(self, tag, attrs):
        start = self.source_offset()
        element = Element(
            tag,
            dict(attrs),
            start,
            start + len(self.get_starttag_text()),
            protected=tag in _PROTECTED or any(n.protected for n in self.stack),
        )
        self.elements.append(element)
        if tag not in _VOID:
            self.stack.append(element)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if self.stack and self.stack[-1].start == self.source_offset():
            element = self.stack.pop()
            element.close = element.end = element.inner

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, -1, -1):
            if self.stack[index].tag == tag:
                element = self.stack[index]
                element.close = self.source_offset()
                end = self.source.find(">", element.close)
                element.end = end + 1
                del self.stack[index:]
                break

    def handle_data(self, data):
        if any(n.protected for n in self.stack):
            return
        start, end = self.source_offset(), self.source_offset() + len(data)
        if self.text_ranges and self.text_ranges[-1][1] == start:
            self.text_ranges[-1] = (self.text_ranges[-1][0], end)
        else:
            self.text_ranges.append((start, end))

    def handle_entityref(self, name):
        self.handle_data("&" + name + ";")

    def handle_charref(self, name):
        self.handle_data("&#" + name + ";")

    def fields(self) -> dict[str, Element]:
        return {
            str(n.attrs["data-slot"]): n
            for n in self.elements
            if n.attrs.get("data-slot")
            and not n.protected
            and n.close >= 0
            and not any(
                c.start > n.start and c.end <= n.end and c.attrs.get("data-slot")
                for c in self.elements
            )
        }


def replace_visible(
    source: str,
    find: str,
    replacement: str,
    *,
    unique: bool = False,
    acknowledge: bool = False,
) -> str | dict[str, str]:
    """Replace text nodes only, optionally refusing ambiguous selections."""
    parsed = DocumentHTML(source)
    matches = []
    # Match visible text while retaining original entity spelling and offsets.
    wanted = html.unescape(find)
    for start, end in parsed.text_ranges:
        raw = source[start:end]
        decoded = ""
        positions = []
        for match in re.finditer(
            r"&(?:#[xX][0-9a-fA-F]+|#\d+|[a-zA-Z][a-zA-Z0-9]+);|.", raw, re.DOTALL
        ):
            value = html.unescape(match.group())
            decoded += value
            positions.extend(
                [(start + match.start(), start + match.end())] * len(value)
            )
        cursor = 0
        while wanted and (at := decoded.find(wanted, cursor)) >= 0:
            matches.append((positions[at][0], positions[at + len(wanted) - 1][1]))
            cursor = at + len(wanted)
    if not matches:
        return {"error": f"Text not found in editable content: {find!r}"}
    if unique and len(matches) != 1:
        return {"error": "Text is ambiguous. Select a longer unique passage."}
    changed_fields = [
        name
        for name, node in parsed.fields().items()
        if any(node.inner <= start and end <= node.close for start, end in matches)
    ]
    for start, end in reversed(matches):
        source = source[:start] + replacement + source[end:]
    return acknowledge_filled_fields(source, changed_fields) if acknowledge else source


def template_fields(source: str) -> list[dict]:
    """Compact, discoverable schema derived from actual editable slots."""
    parsed = DocumentHTML(source)
    rows = []
    for name, node in parsed.fields().items():
        raw = source[node.inner : node.close]
        text = html.unescape(re.sub("<[^>]*>", "", raw)).strip()
        kind = (
            "list"
            if node.tag in {"ul", "ol"}
            else "table"
            if node.tag == "table"
            else "text"
        )
        rows.append(
            {
                "name": name,
                "type": kind,
                "text": text[:1200],
                "required": node.attrs.get("data-required") == "true"
                or node.attrs.get("data-placeholder") == "true"
                or bool(re.search(r"\[(?!\d+\])[^\]\n]+\]", text)),
                "unfilled": node.attrs.get("data-placeholder") == "true"
                or bool(re.search(r"\[(?!\d+\])[^\]\n]+\]", text))
                or (node.attrs.get("data-required") == "true" and not text),
                "truncated": len(text) > 1200,
            }
        )
    return rows


def stamp_template_placeholders(source: str) -> str:
    """Mark editable seed fields for explicit review, not chrome or containers."""
    for node in sorted(
        DocumentHTML(source).fields().values(), key=lambda n: n.start, reverse=True
    ):
        if "data-placeholder" not in node.attrs:
            source = (
                source[: node.inner - 1]
                + ' data-placeholder="true"'
                + source[node.inner - 1 :]
            )
    return source


def acknowledge_filled_fields(source: str, filled: list[str]) -> str:
    names = set(filled)
    for name in filled:
        section = re.fullmatch(r"sections\[(\d+)\]\.(heading|body|bullets)", name)
        table = re.fullmatch(r"tables\[(\d+)\](\.heading)?", name)
        if section:
            suffix = {"heading": "", "body": "-body", "bullets": "-list"}[section[2]]
            names.add(f"section-{section[1]}{suffix}")
        elif table:
            names.add(f"table-{table[1]}" + ("-heading" if table[2] else ""))
        elif name in {"tables_heading", "tables_intro"}:
            names.add(name.replace("_", "-"))
    for name, node in sorted(
        DocumentHTML(source).fields().items(),
        key=lambda item: item[1].start,
        reverse=True,
    ):
        if name in names:
            opening = re.sub(
                r'\sdata-placeholder=["\']true["\']',
                "",
                source[node.start : node.inner],
            )
            source = source[: node.start] + opening + source[node.inner :]
    return source
