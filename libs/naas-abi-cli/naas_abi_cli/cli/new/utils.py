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
    """The package name of the module a scaffold lands in: the nearest package
    at or above ``path`` (which may not exist yet) other than its ``apps`` or
    ``agents`` folder. None outside a package."""
    for folder in (path, *path.parents):
        if folder.name not in ("apps", "agents") and (folder / "__init__.py").is_file():
            return folder.name
    return None
