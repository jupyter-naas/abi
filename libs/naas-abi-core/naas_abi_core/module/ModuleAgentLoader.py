import importlib
import os
from typing import Any

from naas_abi_core.module.ModuleUtils import (
    find_class_module_root_path,
    module_package,
)
from naas_abi_core.utils.Expose import Expose
from naas_abi_core.utils.Logger import logger


class ModuleAgentLoader:
    @staticmethod
    def enabled(agent: type, configuration: Any | None) -> bool:
        """An agent class that names a module configuration flag
        (``enabled_by = "<flag>"``) is loaded only when the module's
        configuration sets that flag; every other agent always is."""
        flag = getattr(agent, "enabled_by", None)
        if not isinstance(flag, str) or not flag:
            return True
        return bool(getattr(configuration, flag, False))

    @classmethod
    def load_agents(
        cls, class_: type, configuration: Any | None = None
    ) -> list[type[Expose]]:
        agents: list[type[Expose]] = []
        module_root_path = find_class_module_root_path(class_)

        agents_path = module_root_path / "agents"

        logger.debug(f"Loading agents from {agents_path}")

        if os.path.exists(agents_path):
            for file in os.listdir(agents_path):
                if file.endswith(".py") and not file.endswith("test.py"):
                    agent_module_path = (
                        f"{module_package(class_)}.agents.{file.replace('.py', '')}"
                    )
                    logger.debug(f"Importing agent module from {agent_module_path}")
                    agent_module = importlib.import_module(agent_module_path)
                    for key, value in agent_module.__dict__.items():
                        if (
                            isinstance(value, type)
                            and issubclass(value, Expose)
                            and value.__module__.split(".")[0]
                            == class_.__module__.split(".")[
                                0
                            ]  # This makes sure we only load agents from the same module.
                        ):
                            if not cls.enabled(value, configuration):
                                logger.debug(
                                    f"Agent {key} is off: its module flag is not set"
                                )
                                continue
                            if not hasattr(key, "New") and hasattr(
                                agent_module, "create_agent"
                            ):
                                getattr(agent_module, key).New = agent_module.create_agent

                            agents.append(getattr(agent_module, key))

        logger.debug(f"Agents: {agents}")

        return agents
