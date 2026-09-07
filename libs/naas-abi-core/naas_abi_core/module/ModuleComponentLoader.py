"""Shared filesystem discovery for module component classes.

Walks ``<module_root>/<folder>/`` the same way ``ModuleAgentLoader`` walks
``agents/``, including nested packages (marketplace pipelines already nest).
"""

from __future__ import annotations

import importlib
import inspect
import os

from naas_abi_core.module.ModuleUtils import find_class_module_root_path
from naas_abi_core.utils.Logger import logger


def _is_component_source(filename: str) -> bool:
    if not filename.endswith(".py"):
        return False
    if filename == "__init__.py":
        return False
    return not filename.endswith("test.py")


def load_subclasses(class_: type, folder: str, base: type) -> list[type]:
    """Return subclasses of ``base`` defined under ``<module_root>/<folder>/``.

    Skips the base class itself, test modules, and classes that were only
    imported into the file (``value.__module__`` must match the file).
    """
    found: list[type] = []
    module_root_path = find_class_module_root_path(class_)
    folder_path = module_root_path / folder
    top_package = class_.__module__.split(".")[0]

    if not os.path.exists(folder_path):
        return found

    logger.debug(f"Loading {folder} from {folder_path}")

    for dirpath, _dirnames, filenames in os.walk(folder_path):
        rel_dir = os.path.relpath(dirpath, folder_path)
        for file in sorted(filenames):
            if not _is_component_source(file):
                continue

            if rel_dir == ".":
                dotted = f"{class_.__module__}.{folder}.{file[:-3]}"
            else:
                subpackage = rel_dir.replace(os.sep, ".")
                dotted = f"{class_.__module__}.{folder}.{subpackage}.{file[:-3]}"

            try:
                imported = importlib.import_module(dotted)
            except Exception as exc:  # noqa: BLE001
                logger.warning(
                    "ModuleComponentLoader: failed to import %s: %s; skipping.",
                    dotted,
                    exc,
                )
                continue

            for _name, value in inspect.getmembers(imported, inspect.isclass):
                if value is base or not issubclass(value, base):
                    continue
                if value.__module__ != imported.__name__:
                    continue
                if value.__module__.split(".")[0] != top_package:
                    continue
                found.append(value)

    logger.debug(f"{folder} classes: {found}")
    return found
