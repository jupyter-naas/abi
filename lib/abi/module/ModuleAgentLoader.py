import importlib
import os
from typing import List

from abi.module.ModuleUtils import find_class_module_root_path
from abi.services.agent.Agent import Agent
from abi.utils.Logger import logger


class ModuleAgentLoader:
    @classmethod
    def load_agents(cls, class_: type):
        agents: List[Agent] = []
        module_root_path = find_class_module_root_path(class_)

        agents_path = module_root_path / "agents"

        logger.debug(f"Loading agents from {agents_path}")

        if os.path.exists(agents_path):
            for file in os.listdir(agents_path):
                if file.endswith(".py") and not file.endswith("test.py"):
                    agent_module_path = (
                        f"{class_.__module__}.agents.{file.replace('.py', '')}"
                    )
                    agent_module = importlib.import_module(agent_module_path)
                    for key, value in agent_module.__dict__.items():
                        if (
                            isinstance(value, type)
                            and issubclass(value, Agent)
                            and value.__module__.split(".")[0]
                            == class_.__module__.split(".")[
                                0
                            ]  # This makes sure we only load agents from the same module.
                        ):
                            if not hasattr(key, "New") and hasattr(
                                agent_module, "create_agent"
                            ):
                                setattr(
                                    getattr(agent_module, key),
                                    "New",
                                    getattr(agent_module, "create_agent"),
                                )

                            agents.append(getattr(agent_module, key))

        logger.debug(f"Agents: {agents}")

        return agents
