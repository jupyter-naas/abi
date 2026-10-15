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


_ABI_MODULE_CLASS = re.compile(r"^class ABIModule\b", re.MULTILINE)


def _defines_abi_module(folder: Path) -> bool:
    try:
        text = (folder / "__init__.py").read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    return _ABI_MODULE_CLASS.search(text) is not None


def module_package_name(path: Path) -> str | None:
    """The dotted package of the module a scaffold lands in: the nearest
    package at or above ``path`` (which may not exist yet) that defines
    ``class ABIModule``, named from its outermost parent package below ``src``
    (``core.research`` for ``src/core/research``). Without one, the nearest
    package other than an ``apps`` or ``agents`` folder. None outside a
    package."""
    folders = (path, *path.parents)
    module = next((f for f in folders if _defines_abi_module(f)), None) or next(
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
        if parent.name == "src" or not (parent / "__init__.py").is_file():
            break
        names.append(parent.name)
    return ".".join(reversed(names))
