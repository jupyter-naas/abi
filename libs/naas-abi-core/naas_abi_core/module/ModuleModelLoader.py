"""Auto-discover and register models from a module's ``models/`` directory.

Each ``.py`` file under ``<module_root>/models/`` (including provider
subdirectories such as ``models/openai/``) should define exactly one class
inheriting from :class:`naas_abi_core.models.Model.ModelDefinition`.
The loader recursively walks the directory tree, imports each file (skipping
``*_test.py`` and ``__init__.py``), and registers every ``ModelDefinition``
subclass it finds (so long as the subclass is defined inside the *same*
top-level package — defensive against ``from other_module import X`` aliases).

Files that don't expose a ``ModelDefinition`` subclass are silently skipped.
"""

from __future__ import annotations

import importlib
import inspect
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

from naas_abi_core.models.Model import CanonicalModelId, Model, ModelDefinition
from naas_abi_core.module.ModuleUtils import find_class_module_root_path
from naas_abi_core.utils.Logger import logger

if TYPE_CHECKING:
    from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry


# Matches ``CANONICAL_ID = CanonicalModelId.FOO`` /
# ``CANONICAL_ID = CanonicalModelId["FOO"]`` / ``CANONICAL_ID = "foo"`` so a
# model file's canonical id can be resolved *without importing it* (importing a
# model file constructs its provider client, which can be slow).
_CANONICAL_ID_ASSIGN_RE = re.compile(r"CANONICAL_ID\s*=")
_CANONICAL_ID_VALUE_RE = re.compile(
    r"CANONICAL_ID\s*=\s*(?:"
    r"CanonicalModelId\.([A-Za-z0-9_]+)"  # enum-member access
    r"|CanonicalModelId\[\s*[\"']([^\"']+)[\"']\s*\]"  # enum-subscript by name
    r"|[\"']([^\"']+)[\"']"  # bare string literal
    r")"
)


def _static_canonical_ids(source: str) -> tuple[set[str], bool]:
    """Best-effort extraction of the canonical-id strings declared via
    ``CANONICAL_ID = ...`` in a model source file, without importing it.

    Returns ``(canonical_ids, fully_resolved)``. ``fully_resolved`` is ``False``
    when at least one ``CANONICAL_ID`` assignment could not be resolved to a
    concrete string — callers must not skip a file that isn't fully resolved.
    """
    ids: set[str] = set()
    resolved = 0
    for member, subscript, literal in _CANONICAL_ID_VALUE_RE.findall(source):
        if member:
            try:
                ids.add(CanonicalModelId[member].value)
                resolved += 1
            except KeyError:
                # Unknown member name — leave unresolved so we import to be safe.
                pass
        elif subscript:
            ids.add(subscript)
            resolved += 1
        elif literal:
            ids.add(literal)
            resolved += 1
    total = len(_CANONICAL_ID_ASSIGN_RE.findall(source))
    return ids, resolved == total


class ModuleModelLoader:
    @classmethod
    def load_models(
        cls,
        class_: type,
        registry: "IModelRegistry",
        include_models: list[str] | None = None,
    ) -> int:
        """Recursively walk ``<module_root>/models/`` and register every
        ``ModelDefinition`` subclass found, including those in provider
        subdirectories (e.g. ``models/openai/``, ``models/anthropic/``).

        When ``include_models`` is provided, only models whose ``CANONICAL_ID``
        is in that list are registered; every other model file is skipped
        *without importing it* — importing a model file constructs its provider
        client (e.g. a Bedrock client), which can add seconds per file. Files
        whose canonical id cannot be resolved statically are imported anyway, so
        the filter never drops a model it can't positively identify.

        Returns the count of successful registrations."""
        module_root_path = find_class_module_root_path(class_)
        models_path = module_root_path / "models"

        if not os.path.exists(models_path):
            return 0

        logger.debug(f"Loading models from {models_path}")
        include_set = set(include_models) if include_models is not None else None
        top_package = class_.__module__.split(".")[0]
        registered = 0

        for dirpath, _dirnames, filenames in os.walk(models_path):
            rel_dir = os.path.relpath(dirpath, models_path)
            for file in sorted(filenames):
                if (
                    not file.endswith(".py")
                    or file.endswith("_test.py")
                    or file == "__init__.py"
                ):
                    continue

                # Build dotted module path relative to the package root.
                # e.g. models/openai/gpt_5.py →
                #      naas_abi_marketplace.ai.openrouter.models.openai.gpt_5
                if rel_dir == ".":
                    model_module_path = f"{class_.__module__}.models.{file[:-3]}"
                else:
                    subpackage = rel_dir.replace(os.sep, ".")
                    model_module_path = (
                        f"{class_.__module__}.models.{subpackage}.{file[:-3]}"
                    )

                # Honour include_models without paying the import cost: if the
                # file's canonical id(s) can be resolved statically and none are
                # in the include set, skip before importing.
                if include_set is not None:
                    try:
                        source = (Path(dirpath) / file).read_text(encoding="utf-8")
                    except OSError:
                        source = None
                    if source is not None:
                        ids, fully_resolved = _static_canonical_ids(source)
                        if fully_resolved and ids and ids.isdisjoint(include_set):
                            logger.debug(
                                "ModuleModelLoader: skipping %s — canonical id(s) "
                                "%s not in include_models.",
                                model_module_path,
                                sorted(ids),
                            )
                            continue

                try:
                    model_module = importlib.import_module(model_module_path)
                except Exception as exc:
                    logger.warning(
                        "ModuleModelLoader: failed to import %s: %s — skipping.",
                        model_module_path,
                        exc,
                    )
                    continue

                for _, value in inspect.getmembers(model_module, inspect.isclass):
                    # Skip the base marker itself and classes pulled in via
                    # ``from other_module import X``-style aliases.
                    if value is ModelDefinition or not issubclass(
                        value, ModelDefinition
                    ):
                        continue
                    if value.__module__ != model_module.__name__:
                        continue
                    if value.__module__.split(".")[0] != top_package:
                        continue

                    canonical_id = getattr(value, "CANONICAL_ID", None)
                    model = getattr(value, "model", None)
                    if canonical_id is None or not isinstance(model, Model):
                        logger.warning(
                            "ModuleModelLoader: %s.%s is a ModelDefinition but is "
                            "missing CANONICAL_ID or a Model instance on ``model`` "
                            "— skipped.",
                            model_module_path,
                            value.__name__,
                        )
                        continue

                    try:
                        registry.register(canonical_id, model)
                        registered += 1
                        logger.debug(
                            "ModuleModelLoader: registered %s.%s as %r (provider=%s).",
                            model_module_path,
                            value.__name__,
                            str(canonical_id),
                            model.provider,
                        )
                    except Exception as exc:
                        logger.warning(
                            "ModuleModelLoader: registration failed for %s.%s "
                            "(canonical_id=%r): %s",
                            model_module_path,
                            value.__name__,
                            str(canonical_id),
                            exc,
                        )

        return registered
