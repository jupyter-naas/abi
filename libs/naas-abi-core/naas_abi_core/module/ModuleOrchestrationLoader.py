import importlib
import os
from typing import List

from naas_abi_core.module.ModuleUtils import find_class_module_root_path
from naas_abi_core.orchestrations.Orchestrations import Orchestrations
from naas_abi_core.utils.Logger import logger


class ModuleOrchestrationLoader:
    @classmethod
    def load_orchestrations(cls, class_: type) -> List[type[Orchestrations]]:
        orchestrations: List[type[Orchestrations]] = []
        module_root_path = find_class_module_root_path(class_)

        orchestrations_path = module_root_path / "orchestrations"

        logger.debug(f"Loading orchestrations from {orchestrations_path}")

        if os.path.exists(orchestrations_path):
            for file in os.listdir(orchestrations_path):
                if file.endswith(".py") and not file.endswith("test.py"):
                    orchestration_module_path = (
                        f"{class_.__module__}.orchestrations.{file.replace('.py', '')}"
                    )
                    logger.debug(f"Importing orchestration module from {orchestration_module_path}")
                    orchestration_module = importlib.import_module(orchestration_module_path)
                    for key, value in orchestration_module.__dict__.items():
                        if (
                            isinstance(value, type)
                            and issubclass(value, Orchestrations)
                            and value.__module__.split(".")[0]
                            == class_.__module__.split(".")[
                                0
                            ]  # This makes sure we only load agents from the same module.
                        ):
                            if not hasattr(value, "New"):
                                logger.error(f"Orchestration {key} in module {class_.__module__} does not have a New method")
                                continue

                            orchestrations.append(getattr(orchestration_module, key))

        logger.debug(f"Orchestrations: {orchestrations}")

        return orchestrations
