"""Auto-discover and register models from a module's ``models/`` directory.

Each ``.py`` file under ``<module_root>/models/`` should define exactly one
class inheriting from :class:`naas_abi_core.models.Model.ModelDefinition`.
The loader walks the directory, imports each file (skipping ``*_test.py``
and ``__init__.py``), and registers every ``ModelDefinition`` subclass it
finds (so long as the subclass is defined inside the *same* top-level
package — defensive against ``from other_module import X`` aliases).

Files that don't expose a ``ModelDefinition`` subclass are silently skipped.
"""

from __future__ import annotations

import importlib
import inspect
import os
from typing import TYPE_CHECKING

from naas_abi_core.models.Model import Model, ModelDefinition
from naas_abi_core.module.ModuleUtils import find_class_module_root_path
from naas_abi_core.utils.Logger import logger

if TYPE_CHECKING:
    from naas_abi_core.services.model_registry.ModelRegistryPort import IModelRegistry


class ModuleModelLoader:
    @classmethod
    def load_models(cls, class_: type, registry: "IModelRegistry") -> int:
        """Walk ``<module_root>/models/*.py`` and register every
        ``ModelDefinition`` subclass found. Returns the count of successful
        registrations."""
        module_root_path = find_class_module_root_path(class_)
        models_path = module_root_path / "models"

        if not os.path.exists(models_path):
            return 0

        logger.debug(f"Loading models from {models_path}")
        top_package = class_.__module__.split(".")[0]
        registered = 0

        for file in sorted(os.listdir(models_path)):
            if (
                not file.endswith(".py")
                or file.endswith("_test.py")
                or file == "__init__.py"
            ):
                continue
            model_module_path = f"{class_.__module__}.models.{file[:-3]}"

            try:
                model_module = importlib.import_module(model_module_path)
            except Exception as exc:
                logger.warning(
                    f"ModuleModelLoader: failed to import {model_module_path}: {exc} — skipping."
                )
                continue

            for _, value in inspect.getmembers(model_module, inspect.isclass):
                # Skip the base marker itself and classes pulled in via
                # ``from other_module import X``-style aliases.
                if value is ModelDefinition or not issubclass(value, ModelDefinition):
                    continue
                if value.__module__ != model_module.__name__:
                    continue
                if value.__module__.split(".")[0] != top_package:
                    continue

                canonical_id = getattr(value, "CANONICAL_ID", None)
                model = getattr(value, "model", None)
                if canonical_id is None or not isinstance(model, Model):
                    logger.warning(
                        f"ModuleModelLoader: {model_module_path}.{value.__name__} "
                        "is a ModelDefinition but is missing CANONICAL_ID or a "
                        "Model instance on ``model`` — skipped."
                    )
                    continue

                try:
                    registry.register(canonical_id, model)
                    registered += 1
                    logger.debug(
                        f"ModuleModelLoader: registered {model_module_path}."
                        f"{value.__name__} as {str(canonical_id)!r} "
                        f"(provider={model.provider})."
                    )
                except Exception as exc:
                    logger.warning(
                        f"ModuleModelLoader: registration failed for "
                        f"{model_module_path}.{value.__name__} "
                        f"(canonical_id={str(canonical_id)!r}): {exc}"
                    )

        return registered
