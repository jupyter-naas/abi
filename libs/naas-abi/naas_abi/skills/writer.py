"""Write one user skill package. The model does not call this on its own.

The create flow calls ``write_skill_package`` only when a person asks for a
package. Prompt rows in Postgres stay on the existing create path. The file
lands under a caller-supplied skills directory as ``<slug>/SKILL.md``, which
``load_user_skills`` already reads. Extra files are written beside it. The
shipped ``naas_abi/skills`` tree and the Nexus Sheets package are refused.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path

from naas_abi.apps.nexus.apps.api.app.services.skills.service import (
    RESERVED_SLUGS,
    normalize_slug,
)

_SKILLS_DIR = Path(__file__).resolve().parent
_SHEETS_SKILLS = _SKILLS_DIR.parent / "agents" / "sheets" / "skills"


def _refuse_shipped(root: Path) -> None:
    destination = root.resolve()
    for blocked in (_SKILLS_DIR.resolve(), _SHEETS_SKILLS.resolve()):
        if destination == blocked or blocked in destination.parents:
            raise ValueError(
                "User skills cannot be written into the shipped package tree"
            )


def _extra_destination(package_dir: Path, raw: str) -> Path:
    """A file path that stays inside ``package_dir``. ``..`` and absolutes fail."""
    text = (raw or "").strip().replace("\\", "/")
    if not text:
        raise ValueError("Skill file path is required")
    if text.startswith("/") or text.startswith("~"):
        raise ValueError("Skill file path must stay inside the package")
    relative = Path(text)
    if relative.is_absolute() or any(part in {"", ".", ".."} for part in relative.parts):
        raise ValueError("Skill file path must stay inside the package")
    if len(relative.parts) == 1 and relative.name.lower() == "skill.md":
        raise ValueError("SKILL.md is written from the skill body")
    destination = (package_dir / relative).resolve()
    base = package_dir.resolve()
    if destination != base and base not in destination.parents:
        raise ValueError("Skill file path must stay inside the package")
    return destination


def write_skill_package(
    root: Path,
    *,
    slug: str,
    name: str,
    description: str,
    when_to_use: str,
    body: str,
    files: Sequence[Mapping[str, str]] | None = None,
) -> Path:
    """Write ``root/<slug>/SKILL.md`` plus any extra ``{path, body}`` files."""
    _refuse_shipped(root)
    normalized = normalize_slug(slug)
    if not normalized or normalized in RESERVED_SLUGS:
        raise ValueError(f"/{normalized or slug} is not a usable skill slug")
    fields = {
        "name": name,
        "description": description,
        "when_to_use": when_to_use,
    }
    for label, value in fields.items():
        text = (value or "").strip()
        if not text:
            raise ValueError(f"{label} is required")
        if "\n" in text or "\r" in text:
            raise ValueError(f"{label} must be a single line")
        fields[label] = text
    procedure = (body or "").strip()
    if not procedure:
        raise ValueError("body is required")
    package_dir = root.resolve() / normalized
    planned: list[tuple[Path, str]] = []
    seen: set[str] = set()
    for item in files or ():
        destination = _extra_destination(package_dir, str(item.get("path", "")))
        key = destination.relative_to(package_dir.resolve()).as_posix()
        if key in seen:
            raise ValueError(f"{key} is already in the skill")
        seen.add(key)
        planned.append((destination, str(item.get("body", "") or "")))
    target = package_dir / "SKILL.md"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        "---\n"
        f"name: {fields['name']}\n"
        f"description: {fields['description']}\n"
        f"when_to_use: {fields['when_to_use']}\n"
        "---\n\n"
        f"{procedure}\n",
        encoding="utf-8",
    )
    for destination, extra_body in planned:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(extra_body, encoding="utf-8")
    return target
