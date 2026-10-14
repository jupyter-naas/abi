"""Catalog loader for Sheets module skills (SKILL.md next to the agent).

The system prompt gets name, description, and when_to_use when that field is
present. The markdown body stays on disk until read_sheets_skill is called.
"""

from __future__ import annotations

import re
from contextvars import ContextVar
from pathlib import Path
from typing import Any

from langchain_core.tools import tool


class _SheetsSkillFlag:
    """Mutable so a tool call can record the read on the turn's shared box.

    ``ContextVar.set`` inside one tool does not survive the next call: each
    call copies the context and drops assignments made inside the copy.
    Mutating an object the turn installed first stays visible.
    """

    loaded: bool = False


# Installed at the start of a sheets turn. Workbook tools refuse until the
# read tool flips ``loaded``.
_sheets_skill_loaded: ContextVar[_SheetsSkillFlag | None] = ContextVar(
    "naas_sheets_skill_loaded", default=None
)


def reset_sheets_skill_loaded() -> None:
    box = _sheets_skill_loaded.get()
    if box is None:
        _sheets_skill_loaded.set(_SheetsSkillFlag())
        return
    box.loaded = False


def note_sheets_skill_loaded() -> None:
    box = _sheets_skill_loaded.get()
    if box is None:
        box = _SheetsSkillFlag()
        _sheets_skill_loaded.set(box)
    box.loaded = True


def sheets_skill_loaded_this_turn() -> bool:
    box = _sheets_skill_loaded.get()
    return bool(box and box.loaded)


def reject_workbook_tool_without_skill() -> dict[str, Any] | None:
    """Block a workbook tool until this turn has read the sheets skill."""
    if sheets_skill_loaded_this_turn():
        return None
    return {
        "error": (
            "Call read_sheets_skill before workbook tools. "
            "The spreadsheet procedure is not in the prompt."
        )
    }

_SKILLS_ROOT = Path(__file__).parent / "skills"
_FRONTMATTER_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")


def _parse_frontmatter(text: str) -> dict[str, str]:
    if not text.startswith("---\n"):
        return {}
    end = text.find("\n---", 4)
    if end < 0:
        return {}
    fields: dict[str, str] = {}
    key: str | None = None
    chunks: list[str] = []

    def flush() -> None:
        nonlocal key, chunks
        if key is None:
            return
        fields[key] = " ".join(part for part in chunks if part).strip()
        key = None
        chunks = []

    for line in text[4:end].splitlines():
        matched = _FRONTMATTER_RE.match(line)
        if matched and not line.startswith((" ", "\t")):
            flush()
            key = matched.group(1)
            value = matched.group(2).strip()
            chunks = [] if value in {">", ">-", "|", "|-", "|+"} else ([value] if value else [])
            continue
        if key is not None and line.startswith((" ", "\t")):
            chunks.append(line.strip())
    flush()
    return fields


def _module_skills() -> list[tuple[dict[str, str], Path]]:
    if not _SKILLS_ROOT.is_dir():
        return []
    found: list[tuple[dict[str, str], Path]] = []
    for path in sorted(_SKILLS_ROOT.glob("*/SKILL.md")):
        found.append((_parse_frontmatter(path.read_text(encoding="utf-8")), path))
    return found


def sheets_skill_catalog_block() -> str:
    """Prompt block: catalog fields only, plus the instruction to read the body."""
    entries = _module_skills()
    lines = [
        "Module skill catalog. Each entry lists name, description, and when_to_use when the skill file has it.",
        "Before the spreadsheet procedure, call read_sheets_skill and follow the body it returns.",
        "The procedure is not in this prompt.",
    ]
    if not entries:
        return "\n".join(lines)
    lines.append("")
    for fm, path in entries:
        name = fm.get("name") or path.parent.name
        lines.append(f"- name: {name}")
        lines.append(f"  description: {fm.get('description', '')}")
        when = (fm.get("when_to_use") or "").strip()
        if when:
            lines.append(f"  when_to_use: {when}")
    return "\n".join(lines)


def read_sheets_skill_body(name: str = "nexus-sheets") -> str:
    """Full SKILL.md for one module skill, including the procedure."""
    needle = (name or "").strip().lower()
    entries = _module_skills()
    if not needle:
        return "Pass the skill name. The shipped skill is nexus-sheets."
    for fm, path in entries:
        skill_name = (fm.get("name") or path.parent.name).lower()
        if needle in {skill_name, path.parent.name.lower()}:
            return path.read_text(encoding="utf-8")
    available = ", ".join(
        (fm.get("name") or path.parent.name) for fm, path in entries
    ) or "none"
    return f"Skill '{name}' not found. Available module skills: {available}"


def make_read_sheets_skill_tool():
    @tool
    def read_sheets_skill(name: str = "nexus-sheets") -> str:
        """Read the full Nexus Sheets skill body before the spreadsheet procedure.

        Args:
            name: Skill name from the catalog. The shipped skill is nexus-sheets.
        """
        text = read_sheets_skill_body(name)
        if text.startswith(("Skill '", "Pass the skill")):
            return text
        note_sheets_skill_loaded()
        return text

    return read_sheets_skill
