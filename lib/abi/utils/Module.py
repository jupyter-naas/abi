from abc import ABC
from abi.services.triple_store.TripleStorePorts import OntologyEvent
from abi.services.agent.Agent import Agent
from abi import logger
from typing import Callable, List, Any
import os
import importlib
import glob


class IModule(ABC):
    """Base interface class for ABI modules.

    This class serves as the base interface for all modules in the src/modules directory.

    The IModule class provides a default loading mechanism.


    The default loading mechanism will:
    1. Load all agents from the module's 'agents' directory
    2. Initialize module configuration and state

    Attributes:
        agents (List[Agent]): List of agents loaded from the module
    """

    agents: List[Agent]
    triggers: List[tuple[tuple[Any, Any, Any], OntologyEvent, Callable]]
    ontologies: List[str]

    def __init__(self, module_path: str, module_import_path: str, imported_module: Any):
        self.module_path = module_path
        self.module_import_path = module_import_path
        self.imported_module = imported_module
        self.triggers = []
        self.ontologies = []
        self.agents = []

    def check_requirements(self):
        if hasattr(self.imported_module, "requirements"):
            if not self.imported_module.requirements():
                logger.error(f"❌ Module {self.module_import_path} failed to meet requirements.")
                raise SystemExit(f"Application crashed due to module loading failure: {self.module_import_path}")
        
    def load(self):
        try:
            self.check_requirements()
            # self.__load_agents()
            self.__load_triggers()
            self.__load_ontologies()
        except Exception as e:
            logger.error(f"❌ Critical error loading module {self.module_import_path}: {e}")
            raise SystemExit(f"Application crashed due to module loading failure: {self.module_import_path}")

    def load_agents(self):
        try:
            self.__load_agents()
        except Exception as e:
            import traceback
            logger.error(f"❌ Critical error loading agents for module {self.module_import_path}: {e}")
            traceback.print_exc()
            raise SystemExit(f"Application crashed due to agent loading failure: {self.module_import_path}")

    def __load_agents(self):
        # Load agents
        self.agents = []
        loaded_agent_names = set()

        # Find all agent files recursively
        for root, _, files in os.walk(self.module_path):
            for file in files:
                if file.endswith("Agent.py") and not file.endswith("Agent_test.py"):
                    # Get relative path from module root to agent file
                    rel_path = os.path.relpath(root, self.module_path)
                    # Convert path to import format
                    import_path = rel_path.replace(os.sep, ".")
                    if import_path == ".":
                        agent_path = self.module_import_path + "." + file[:-3]
                    else:
                        agent_path = self.module_import_path + "." + import_path + "." + file[:-3]

                    module = importlib.import_module(agent_path)
                    if hasattr(module, "create_agent"):
                        agent = module.create_agent()
                        if agent is not None:
                            agent_name = getattr(agent, "name", None)
                            if agent_name and agent_name not in loaded_agent_names:
                                self.agents.append(agent)
                                loaded_agent_names.add(agent_name)
                            else:
                                logger.warning(f"Skipping duplicate agent: {agent_name}")

    def __load_triggers(self):
        if os.path.exists(os.path.join(self.module_path, "triggers.py")):
            module = importlib.import_module(self.module_import_path + ".triggers")
            if hasattr(module, "triggers"):
                self.triggers = module.triggers

    def __load_ontologies(self):
        if os.path.exists(os.path.join(self.module_path, "ontologies")):
            for file in glob.glob(
                os.path.join(self.module_path, "ontologies", "**", "*.ttl"),
                recursive=True,
            ):
                self.ontologies.append(file)

    def on_initialized(self):
        if hasattr(self.imported_module, "on_initialized"):
            self.imported_module.on_initialized()
