import importlib
import os

from naas_abi_core.module.ModuleUtils import (
    find_class_module_root_path,
    module_package,
)
from naas_abi_core.orchestrations.Orchestrations import Orchestrations
from naas_abi_core.utils.LegacyExtras import (
    LEGACY_NOTICE,
    install_hint,
    legacy_extra_of,
)
from naas_abi_core.utils.Logger import logger


class ModuleOrchestrationLoader:
    @classmethod
    def load_orchestrations(cls, class_: type) -> list[type[Orchestrations]]:
        orchestrations: list[type[Orchestrations]] = []
        # Files left out because a legacy extra (Dagster) is not installed.
        skipped: dict[str, list[str]] = {}
        module_root_path = find_class_module_root_path(class_)

        orchestrations_path = module_root_path / "orchestrations"

        logger.debug(f"Loading orchestrations from {orchestrations_path}")

        if os.path.exists(orchestrations_path):
            for file in os.listdir(orchestrations_path):
                if file.endswith(".py") and not file.endswith("test.py"):
                    orchestration_module_path = (
                        f"{module_package(class_)}.orchestrations.{file.replace('.py', '')}"
                    )
                    logger.debug(f"Importing orchestration module from {orchestration_module_path}")
                    try:
                        orchestration_module = importlib.import_module(
                            orchestration_module_path
                        )
                    except ModuleNotFoundError as error:
                        extra = legacy_extra_of(error)
                        if extra is None:
                            raise
                        skipped.setdefault(extra, []).append(file)
                        continue
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

        for extra, files in skipped.items():
            # Info, not a warning: orchestrations only run in the Dagster app,
            # which a NATS project does without.
            logger.info(
                f"Module {module_package(class_)}: orchestrations not loaded, "
                f"the `{extra}` extra is not installed ({', '.join(sorted(files))}). "
                f"{install_hint(extra)} {LEGACY_NOTICE}"
            )

        logger.debug(f"Orchestrations: {orchestrations}")

        return orchestrations
