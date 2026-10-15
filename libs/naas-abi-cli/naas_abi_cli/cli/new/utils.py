import re
from pathlib import Path


def _split_words(text: str) -> list[str]:
    # Insert a space at every lower-or-digit → upper transition so PascalCase
    # and camelCase split correctly. Then findall splits on any non-alphanumeric.
    spaced = re.sub(r"([a-z0-9])([A-Z])", r"\1 \2", text)
    return re.findall(r"[A-Za-z0-9]+", spaced)


def to_pascal_case(text: str) -> str:
    return "".join(word.capitalize() for word in _split_words(text))


def to_snake_case(text: str) -> str:
    return "_".join(word.lower() for word in _split_words(text))


def to_kebab_case(text: str) -> str:
    return "-".join(word.lower() for word in _split_words(text))


def module_package_name(path: Path) -> str | None:
    """The dotted package of the module a scaffold lands in: the nearest
    package at or above ``path`` (which may not exist yet) whose
    ``__init__.py`` defines ``ABIModule``, named from its outermost parent
    package (``core.research`` for ``src/core/research``). Without one, the
    nearest package other than an ``apps`` or ``agents`` folder. None outside a
    package."""
    folders = (path, *path.parents)
    module = next(
        (
            f
            for f in folders
            if (f / "__init__.py").is_file()
            and "class ABIModule" in (f / "__init__.py").read_text(encoding="utf-8")
        ),
        None,
    ) or next(
        (
            f
            for f in folders
            if f.name not in ("apps", "agents") and (f / "__init__.py").is_file()
        ),
        None,
    )
    if module is None:
        return None
    names = [module.name]
    for parent in module.parents:
        if not (parent / "__init__.py").is_file():
            break
        names.append(parent.name)
    return ".".join(reversed(names))
