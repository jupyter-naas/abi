"""Read-only catalog of skills shipped with the package.

Each package is ``naas_abi/skills/<slug>/SKILL.md`` with frontmatter
``name``, ``description``, and ``when_to_use``. The markdown below the
frontmatter is the body. Callers that build a chat prompt must keep
that body out of the prompt and load it on demand.

The sheets builtin reads its body and extra files from the existing
``agents/sheets/skills/nexus-sheets`` package. That package stays where
it is. User-written packages are loaded from a directory the caller
passes in. They are not part of the shipped tree.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

# Stable UI order. Directories not listed here sort after these, by slug.
_PREFERRED_ORDER = (
    "sheets",
    "slides",
    "documents",
    "web-research",
    "skill-creator",
)

# Catalog rows whose /slug turn goes to an office agent. The procedure body
# stays out of the current agent's prompt when that agent is on the roster.
OFFICE_HANDOFF_SLUGS = frozenset({"sheets", "slides", "documents"})

_REQUIRED = ("name", "description", "when_to_use")

# Disclosure budget for one chat catalog. Descriptions are capped first.
# An entry that still does not fit is dropped whole. Bodies are not a field.
DEFAULT_CATALOG_BUDGET = 8000
DEFAULT_DESCRIPTION_CAP = 250


@dataclass(frozen=True)
class CatalogEntry:
    """One enabled skill as the chat catalog may disclose it. No body."""

    slug: str
    name: str
    description: str
    when_to_use: str = ""


@dataclass(frozen=True)
class BundledSkill:
    slug: str
    name: str
    description: str
    when_to_use: str
    body: str

    @property
    def record_id(self) -> str:
        return f"bundled-{self.slug}"


@dataclass(frozen=True)
class ModuleSkill:
    module_name: str
    skill: BundledSkill
    root: Path

    @property
    def reference(self) -> str:
        return f"{self.module_name}:{self.skill.slug}"


def load_module_skills(modules: dict) -> dict[str, ModuleSkill]:
    """Catalog only packages discovered by loaded ABI modules."""
    found: dict[str, ModuleSkill] = {}
    for module_name, module in modules.items():
        for raw in module.skills:
            path = Path(raw)
            skill = _load_one(path)
            root = (
                sheets_package_root()
                if path.resolve()
                == (Path(__file__).parent / "sheets/SKILL.md").resolve()
                else path.parent
            )
            item = ModuleSkill(module_name, skill, root)
            if item.reference in found:
                raise ValueError(f"Duplicate module skill reference: {item.reference}")
            found[item.reference] = item
    return found


def parse_frontmatter(
    text: str, path: Path | None = None
) -> tuple[dict[str, str], str]:
    """Split YAML-ish frontmatter from a SKILL.md body.

    Values are single-line. A missing closer or a missing required field
    raises ``ValueError`` when ``path`` is set (shipped and user packages).
    """
    label = str(path) if path is not None else "SKILL.md"
    if not text.startswith("---\n"):
        raise ValueError(f"{label} is missing frontmatter")
    end = text.find("\n---\n", 4)
    if end < 0:
        raise ValueError(f"{label} has unclosed frontmatter")
    fields: dict[str, str] = {}
    for line in text[4:end].splitlines():
        if not line.strip():
            continue
        key, sep, value = line.partition(":")
        if not sep or not key.strip():
            raise ValueError(f"{label} has an invalid frontmatter line: {line}")
        fields[key.strip()] = value.strip().strip("\"'")
    if path is not None:
        missing = [key for key in _REQUIRED if not fields.get(key, "").strip()]
        if missing:
            raise ValueError(f"{label} is missing {', '.join(missing)}")
    return fields, text[end + 5 :].strip()


def _split_frontmatter(text: str, path: Path) -> tuple[dict[str, str], str]:
    return parse_frontmatter(text, path)


def sheets_package_root() -> Path:
    """Existing Nexus Sheets package. Do not move it."""
    return (
        Path(__file__).resolve().parents[1]
        / "agents"
        / "sheets"
        / "skills"
        / "nexus-sheets"
    )


def _sheets_package_body() -> str:
    path = sheets_package_root() / "SKILL.md"
    _fields, body = parse_frontmatter(path.read_text(encoding="utf-8"), None)
    if not body:
        raise ValueError(f"{path} has an empty body")
    return body


def _load_one(path: Path) -> BundledSkill:
    fields, body = _split_frontmatter(path.read_text(encoding="utf-8"), path)
    shipped_sheets = Path(__file__).resolve().parent / "sheets" / "SKILL.md"
    if path.resolve() == shipped_sheets.resolve():
        body = _sheets_package_body()
    if not body:
        raise ValueError(f"{path} has an empty body")
    return BundledSkill(
        slug=path.parent.name,
        name=fields["name"].strip(),
        description=fields["description"].strip(),
        when_to_use=fields["when_to_use"].strip(),
        body=body,
    )


def load_bundled_skills() -> tuple[BundledSkill, ...]:
    """Every shipped skill, in display order."""
    root = Path(__file__).resolve().parent
    found = [_load_one(path) for path in sorted(root.glob("*/SKILL.md"))]
    order = {slug: index for index, slug in enumerate(_PREFERRED_ORDER)}
    found.sort(key=lambda skill: (order.get(skill.slug, len(order)), skill.slug))
    return tuple(found)


def bundled_by_id(skill_id: str) -> BundledSkill | None:
    needle = (skill_id or "").strip()
    if not needle:
        return None
    return next(
        (skill for skill in load_bundled_skills() if skill.record_id == needle), None
    )


def load_user_skills(root: Path | None) -> tuple[BundledSkill, ...]:
    """SKILL.md packages under ``root/<slug>/``. Missing directories are empty."""
    if root is None or not root.is_dir():
        return ()
    found: list[BundledSkill] = []
    for path in sorted(root.glob("*/SKILL.md")):
        found.append(_load_one(path))
    return tuple(found)


def truncate_description(value: str, cap: int = DEFAULT_DESCRIPTION_CAP) -> str:
    text = (value or "").strip()
    cap = max(cap, 0)
    if len(text) <= cap:
        return text
    return text[:cap]


def _render_entry(entry: CatalogEntry, description_cap: int) -> str:
    description = truncate_description(entry.description, description_cap)
    when = (entry.when_to_use or "").strip()
    return (
        f"- slug: {entry.slug}\n"
        f"  name: {entry.name}\n"
        f"  description: {description}\n"
        f"  when_to_use: {when}"
    )


def render_catalog(
    entries: Sequence[CatalogEntry],
    *,
    budget: int = DEFAULT_CATALOG_BUDGET,
    description_cap: int = DEFAULT_DESCRIPTION_CAP,
    header: str = "",
) -> str:
    """Disclosure text that fits ``budget``.

    Descriptions are truncated to ``description_cap``. A skill that still
    does not fit is omitted. Later, smaller skills can still fit. The entry
    type has no body, so a procedure cannot be cut into the block.
    """
    pieces: list[str] = []
    used = len(header)
    for entry in entries:
        block = _render_entry(entry, description_cap)
        if pieces or header and not header.endswith("\n"):
            extra = 1 + len(block)
        else:
            extra = len(block)
        if used + extra > budget:
            continue
        pieces.append(block)
        used += extra
    body = "\n".join(pieces)
    if header and body and not header.endswith("\n"):
        return header + "\n" + body
    return header + body


def package_root(slug: str) -> Path | None:
    """Directory of a shipped package, or None when the slug has no files."""
    if slug == "sheets":
        root = sheets_package_root()
    else:
        root = Path(__file__).resolve().parent / slug
    if (root / "SKILL.md").is_file():
        return root
    return None


def _list_files(root: Path) -> tuple[str, ...]:
    found: list[str] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith(".") or "__pycache__" in path.parts:
            continue
        if path.suffix == ".pyc":
            continue
        found.append(path.relative_to(root).as_posix())
    return tuple(found)


def list_package_files(slug: str) -> tuple[str, ...]:
    """Real files for a shipped package. Unknown slugs have no tree."""
    root = package_root(slug)
    if root is None:
        return ()
    return _list_files(root)


def list_directory_files(root: Path) -> tuple[str, ...]:
    if not root.is_dir():
        return ()
    return _list_files(root)


def read_package_file(slug: str, relative: str) -> str | None:
    """File text for a shipped package path. Traversal and missing files are None."""
    root = package_root(slug)
    return _read_under(root, relative) if root is not None else None


def read_directory_file(root: Path, relative: str) -> str | None:
    return _read_under(root, relative)


def _read_under(root: Path | None, relative: str) -> str | None:
    if root is None:
        return None
    rel = Path(relative)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    candidate = (root / rel).resolve()
    base = root.resolve()
    if candidate != base and base not in candidate.parents:
        return None
    if not candidate.is_file():
        return None
    return candidate.read_text(encoding="utf-8")
