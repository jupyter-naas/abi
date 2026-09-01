"""Office-agent skills shipped with ABI (slides now; docs/sheets later).

Skill files live in this directory as ``<name>/SKILL.md`` with YAML frontmatter,
same layout as Cursor and the zen tenant pointer. Zen keeps config and a
pointer; ABI is the carrier.
"""

from __future__ import annotations

import re
from pathlib import Path

from langchain_core.tools import tool

_SKILLS_DIR = Path(__file__).resolve().parent


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\n(.*?)\n---\n?(.*)", text, re.DOTALL)
    if not match:
        return {}, text
    fm_raw, body = match.group(1), match.group(2)
    fm: dict[str, str] = {}
    current_key: str | None = None
    current_val: list[str] = []
    for line in fm_raw.splitlines():
        if re.match(r"^\w[\w-]*\s*:", line) and not line.startswith(" "):
            if current_key:
                fm[current_key] = " ".join(current_val).strip()
            parts = line.split(":", 1)
            current_key = parts[0].strip()
            current_val = [parts[1].strip().lstrip(">-").strip()]
        elif line.startswith("  ") and current_key:
            current_val.append(line.strip())
    if current_key:
        fm[current_key] = " ".join(current_val).strip()
    return fm, body.strip()


def list_office_skill_records() -> list[tuple[str, dict[str, str], Path]]:
    results: list[tuple[str, dict[str, str], Path]] = []
    if not _SKILLS_DIR.exists():
        return results
    for skill_dir in sorted(_SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir():
            continue
        skill_file = skill_dir / "SKILL.md"
        if not skill_file.exists():
            continue
        text = skill_file.read_text(encoding="utf-8")
        fm, _ = _parse_frontmatter(text)
        name = fm.get("name") or skill_dir.name
        results.append((name, fm, skill_file))
    return results


def load_office_skill(name: str) -> str:
    """Return the full SKILL.md text for ``name``, or empty string."""
    wanted = (name or "").strip().lower()
    if not wanted:
        return ""
    for skill_name, _fm, path in list_office_skill_records():
        if skill_name.lower() == wanted or path.parent.name.lower() == wanted:
            return path.read_text(encoding="utf-8")
    return ""


def office_skill_tools() -> list:
    @tool
    def list_office_skills() -> str:
        """List ABI office skills (slides now). Docs and sheets are not registered yet."""
        rows = list_office_skill_records()
        if not rows:
            return "No office skills are registered."
        lines = ["ABI office skills:"]
        for skill_name, fm, _path in rows:
            desc = fm.get("description") or ""
            lines.append(f"- {skill_name}: {desc}" if desc else f"- {skill_name}")
        return "\n".join(lines)

    @tool
    def read_office_skill(name: str) -> str:
        """Read the full ABI office skill (e.g. slides)."""
        text = load_office_skill(name)
        if not text:
            return f"Unknown office skill '{name}'. Call list_office_skills."
        return text

    return [list_office_skills, read_office_skill]
