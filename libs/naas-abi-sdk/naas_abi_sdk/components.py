"""Workflows and pipelines of a remote module: names, discovery and construction.

Standard library only, so ``BaseModule`` can import it without the extras the
base classes need (``naas_abi_sdk.workflow``, ``naas_abi_sdk.pipeline``).

A component's name is the slug of its class name (``FooBarWorkflow`` is
``foo_bar_workflow``), as core's ``process_route_slug`` computes it. It is one
NATS subject token, unique per kind in a module.
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

_CAMEL_ACRONYM = re.compile(r"([A-Z]+)([A-Z][a-z])")
_CAMEL_BOUNDARY = re.compile(r"([a-z0-9])([A-Z])")
# One NATS subject token: no dots, wildcards or spaces.
COMPONENT_NAME = re.compile(r"[a-z_][a-z0-9_]{0,63}")
# Folders that hold no component: tests and caches.
_SKIPPED_DIRS = {"tests", "__pycache__"}


def component_slug(name: str) -> str:
    """The stable name of a class: snake case, one NATS subject token."""
    stepped = _CAMEL_ACRONYM.sub(r"\1_\2", name)
    stepped = _CAMEL_BOUNDARY.sub(r"\1_\2", stepped)
    slug = stepped.replace(" ", "_").replace("-", "_").lower()
    if not COMPONENT_NAME.fullmatch(slug):
        raise ValueError(
            f"Class name {name!r} gives the component name {slug!r}: 1 to 64 "
            "lowercase ASCII letters, digits or '_', not starting with a digit "
            "(it is a NATS subject token)"
        )
    return slug


def by_name(kind: str, classes: Any) -> dict[str, type]:
    """``classes`` keyed by their slug, sorted; two with one slug are refused."""
    named: dict[str, type] = {}
    for cls in classes:
        slug = component_slug(cls.__name__)
        if slug in named:
            raise ValueError(
                f"Two {kind}s are named {slug!r}: "
                f"{named[slug].__module__}.{named[slug].__name__} and "
                f"{cls.__module__}.{cls.__name__}. Rename one class."
            )
        named[slug] = cls
    return dict(sorted(named.items()))


def module_package(module_type: type) -> tuple[Path, str] | None:
    """The folder and dotted name of the package ``module_type`` is defined in."""
    module = sys.modules.get(module_type.__module__)
    file = getattr(module, "__file__", None)
    if not file:
        return None
    path = Path(file).resolve()
    if path.name == "__init__.py":
        return path.parent, module_type.__module__
    return path.parent, module_type.__module__.rpartition(".")[0]


def _is_component_source(filename: str) -> bool:
    return (
        filename.endswith(".py")
        and filename != "__init__.py"
        and filename != "conftest.py"
        and not filename.endswith("_test.py")
        and not filename.startswith("test_")
    )


def component_files(module_type: type, folder: str) -> list[str]:
    """Dotted names of the modules under ``<package>/<folder>/``, recursively,
    tests and caches left out."""
    located = module_package(module_type)
    if located is None or not (located[0] / folder).is_dir():
        return []
    root = located[0] / folder
    dotted: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(
            d for d in dirnames if d not in _SKIPPED_DIRS and not d.startswith(".")
        )
        parts = [located[1], folder, *Path(dirpath).relative_to(root).parts]
        dotted.extend(
            ".".join([*parts, name[:-3]])
            for name in sorted(filenames)
            if _is_component_source(name)
        )
    return dotted


def discover_components(
    module_type: type, folder: str, load_base: Callable[[], type]
) -> list[type]:
    """Subclasses of the base defined under ``<package>/<folder>/``.

    ``load_base`` imports the base class only when the folder holds code, so a
    module without workflows or pipelines needs no extra. Classes that are
    only imported into a file, abstract ones and the base itself are skipped.
    """
    dotted_names = component_files(module_type, folder)
    if not dotted_names:
        return []
    base = load_base()
    found: list[type] = []
    for dotted in dotted_names:
        try:
            imported = importlib.import_module(dotted)
        except ImportError as exc:
            # A missing extra or dependency: say which file needs it.
            raise ImportError(
                f"Cannot import {dotted} while discovering {folder}/: {exc}"
            ) from exc
        for _, value in inspect.getmembers(imported, inspect.isclass):
            if value is base or not issubclass(value, base):
                continue
            if value.__module__ != imported.__name__ or inspect.isabstract(value):
                continue
            found.append(value)
    return found


def configuration_class(cls: type) -> type | None:
    """``<Name>Configuration`` next to the class, else a nested ``Configuration``."""
    module = sys.modules.get(cls.__module__)
    candidate = getattr(module, f"{cls.__name__}Configuration", None)
    if isinstance(candidate, type):
        return candidate
    nested = getattr(cls, "Configuration", None)
    return nested if isinstance(nested, type) else None
