"""Slide commands on git-backed HTML.

Rename and title verbs match Documents: one named command, two callers
(HTTP and the agent). Other slide mutations stay on dedicated routes
this pass. See ``naas_abi/apps/nexus/apps/api/app/services/slides/COMMANDS.md``.
"""

from __future__ import annotations

import html as html_lib
import re
from typing import Any

_TITLE_TAG_RE = re.compile(r"<title\b[^>]*>.*?</title>", re.IGNORECASE | re.DOTALL)
_H1_OPEN_RE = re.compile(r"<h1\b[^>]*>", re.IGNORECASE)
_H1_FULL_RE = re.compile(r"<h1\b[^>]*>.*?</h1>", re.IGNORECASE | re.DOTALL)
_SECTION_OPEN_RE = re.compile(r"<section\b", re.IGNORECASE)

KNOWN_COMMANDS = frozenset(
    {
        "update_title",
        "rename_deck",
    }
)


def _escape(text: str) -> str:
    return html_lib.escape(text or "", quote=False)


def update_deck_title(html: str, title: str) -> str | dict[str, str]:
    """Set the tab ``<title>`` and the first cover ``<h1>`` to the same name.

    ``update_title`` and ``rename_deck`` share this HTML step. The project
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
    if not changed:
        return {"error": "No deck title or cover heading to update."}
    return next_html


def last_rename_deck_title(requests: list[dict[str, Any]]) -> str:
    """Last ``rename_deck`` title in a command batch, or empty."""
    title = ""
    for raw in requests:
        if not isinstance(raw, dict):
            continue
        if str(raw.get("type") or "").strip().lower() != "rename_deck":
            continue
        candidate = str(raw.get("title") or raw.get("text") or "").strip()
        if candidate:
            title = candidate
    return title


def apply_slide_commands(html: str, requests: list[dict[str, Any]]) -> dict[str, Any]:
    """Apply an ordered list of slide commands. Atomic: first error aborts.

    This pass only implements ``rename_deck`` and ``update_title``. Insert,
    delete, duplicate, and reorder stay on their dedicated routes.
    """
    if not isinstance(requests, list) or not requests:
        return {"error": "requests must be a non-empty list of command objects"}
    next_html = html
    applied: list[str] = []
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
        result = update_deck_title(
            next_html, str(raw.get("title") or raw.get("text") or "")
        )
        if isinstance(result, dict):
            return result
        next_html = result
        applied.append(typ)

    section_count = len(_SECTION_OPEN_RE.findall(next_html))
    return {
        "ok": True,
        "html": next_html,
        "applied": applied,
        "section_index": 0,
        "section_count": section_count,
        "ids": [None] * section_count,
        "slides": [],
    }
