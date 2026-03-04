from __future__ import annotations

import glob
import os
from typing import Dict, List, cast

from fastapi import FastAPI
from naas_abi_core import logger
from naas_abi_core.engine.engine_configuration.EngineConfiguration import \
    GlobalConfig
from naas_abi_core.engine.EngineProxy import EngineProxy
from naas_abi_core.integration.integration import Integration
from naas_abi_core.module.ModuleAgentLoader import ModuleAgentLoader
from naas_abi_core.module.ModuleOrchestrationLoader import \
    ModuleOrchestrationLoader
from naas_abi_core.module.ModuleUtils import find_class_module_root_path
from naas_abi_core.orchestrations.Orchestrations import Orchestrations
from naas_abi_core.pipeline.pipeline import Pipeline
from naas_abi_core.services.agent.Agent import Agent
from naas_abi_core.workflow.workflow import Workflow
from pydantic import BaseModel, ConfigDict
from typing_extensions import Generic, Self, TypeVar


class ModuleDependencies:
    __modules: List[str]
    __services: List[type]

    def __init__(self, modules: List[str], services: List[type]):
        self.__modules = modules
        self.__services = services

    def _get_modules(self) -> List[str]:
        return self.__modules

    def _set_modules(self, modules: List[str]) -> None:
        self.__modules = modules

    modules = property(_get_modules, _set_modules)

    def _get_services(self) -> List[type]:
        return self.__services

    def _set_services(self, services: List[type]) -> None:
        self.__services = services

    services = property(_get_services, _set_services)


class ModuleConfiguration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    global_config: GlobalConfig


TConfig = TypeVar("TConfig", bound=ModuleConfiguration)


class BaseModule(Generic[TConfig]):
    """Base interface class for ABI modules."""

    _instances: Dict[type, Self] = {}

    _engine: EngineProxy
    _configuration: TConfig
    dependencies: ModuleDependencies = ModuleDependencies(modules=[], services=[])

    __ontologies: List[str] = []
    __agents: List[type[Agent]] = []
    __integrations: List[Integration] = []
    __workflows: List[Workflow] = []
    __pipelines: List[Pipeline] = []
    __orchestrations: List[type[Orchestrations]] = []

    def __init__(self, engine: EngineProxy, configuration: TConfig):
        assert isinstance(configuration, ModuleConfiguration), (
            "configuration must be an instance of ModuleConfiguration"
        )
        logger.debug(f"Initializing module {self.__module__.split('.')[0]}")
        self.module_path = self.__module__.split(".")[0]
        self.module_root_path = find_class_module_root_path(self.__class__).as_posix()
        self._engine = engine
        self._configuration = configuration

        assert hasattr(self.__class__, "Configuration"), (
            "BaseModule must have a Configuration class"
        )
        assert type(self.__class__.Configuration) is type(ModuleConfiguration), (
            "BaseModule.Configuration must be a subclass of ModuleConfiguration"
        )

        self_instance: Self = cast(Self, self)

        self._instances[self.__class__] = self_instance

    @classmethod
    def get_dependencies(cls) -> List[str]:
        """Return the list of module dependencies."""
        return getattr(cls, "dependencies", [])

    @classmethod
    def get_instance(cls) -> Self:
        if cls not in cls._instances:
            raise ValueError(f"Module {cls} not initialized")
        return cls._instances[cls]

    @property
    def engine(self) -> EngineProxy:
        return self._engine

    @property
    def configuration(self) -> TConfig:
        return self._configuration

    @property
    def ontologies(self) -> List[str]:
        return self.__ontologies

    @property
    def agents(self) -> List[type[Agent]]:
        return self.__agents

    @property
    def integrations(self) -> List[Integration]:
        return self.__integrations

    @property
    def workflows(self) -> List[Workflow]:
        return self.__workflows

    @property
    def pipelines(self) -> List[Pipeline]:
        return self.__pipelines

    @property
    def orchestrations(self) -> List[type[Orchestrations]]:
        return self.__orchestrations

    def on_load(self):
        logger.debug(f"on_load for module {self.__module__.split('.')[0]}")
        self.__load_ontologies()

        self.__agents = ModuleAgentLoader.load_agents(self.__class__)
        self.__orchestrations = ModuleOrchestrationLoader.load_orchestrations(
            self.__class__
        )

    def on_initialized(self):
        """
        Called after all modules have been loaded and the engine is fully initialized.

        Use this method to perform post-initialization steps that require other modules,
        services, or ontologies to be available and loaded.
        """
        logger.debug(f"on_initialized for module {self.__module__.split('.')[0]}")

    def on_unloaded(self):
        pass

    def api(self, app: FastAPI) -> None:
        """
        Override this method in a module subclass to provide custom API endpoints 
        via FastAPI's APIRouter. By default, this method does nothing.

        Args:
            app (FastAPI): The FastAPI app instance to register the API endpoints on.
        """
        pass

    def __load_ontologies(self):
        if os.path.exists(os.path.join(self.module_root_path, "ontologies")):
            for file in glob.glob(
                os.path.join(self.module_root_path, "ontologies", "**", "*.ttl"),
                recursive=True,
            ):
                self.ontologies.append(file)


# class IModule(ABC):
#     """Base interface class for ABI modules.

#     This class serves as the base interface for all modules in the src/modules directory.

#     The IModule class provides a default loading mechanism.


#     The default loading mechanism will:
#     1. Load all agents from the module's 'agents' directory
#     2. Initialize module configuration and state

#     Attributes:
#         agents (List[Agent]): List of agents loaded from the module
#     """

#     agents: List[Agent]
#     triggers: List[tuple[tuple[Any, Any, Any], OntologyEvent, Callable]]
#     ontologies: List[str]

#     def __init__(self, module_path: str, module_import_path: str, imported_module: Any):
#         self.module_path = module_path
#         self.module_import_path = module_import_path
#         self.imported_module = imported_module
#         self.triggers = []
#         self.ontologies = []
#         self.agents = []

#     def check_requirements(self):
#         if hasattr(self.imported_module, "requirements"):
#             if not self.imported_module.requirements():
#                 logger.error(f"❌ Module {self.module_import_path} failed to meet requirements.")
#                 raise SystemExit(f"Application crashed due to module loading failure: {self.module_import_path}")

#     def load(self):
#         try:
#             self.check_requirements()
#             # self.__load_agents()
#             self.__load_triggers()
#             self.__load_ontologies()
#         except Exception as e:
#             logger.error(f"❌ Critical error loading module {self.module_import_path}: {e}")
#             raise SystemExit(f"Application crashed due to module loading failure: {self.module_import_path}")

#     def load_agents(self):
#         try:
#             self.__load_agents()
#         except Exception as e:
#             import traceback
#             logger.error(f"❌ Critical error loading agents for module {self.module_import_path}: {e}")
#             traceback.print_exc()
#             raise SystemExit(f"Application crashed due to agent loading failure: {self.module_import_path}")

#     def __load_agents(self):
#         # Load agents
#         self.agents = []
#         loaded_agent_names = set()

#         # Find all agent files recursively
#         for root, _, files in os.walk(self.module_path):
#             for file in files:
#                 if file.endswith("Agent.py") and not file.endswith("Agent_test.py"):
#                     # Get relative path from module root to agent file
#                     rel_path = os.path.relpath(root, self.module_path)
#                     # Convert path to import format
#                     import_path = rel_path.replace(os.sep, ".")
#                     if import_path == ".":
#                         agent_path = self.module_import_path + "." + file[:-3]
#                     else:
#                         agent_path = self.module_import_path + "." + import_path + "." + file[:-3]

#                     module = importlib.import_module(agent_path)
#                     if hasattr(module, "create_agent"):
#                         agent = module.create_agent()
#                         if agent is not None:
#                             agent_name = getattr(agent, "name", None)
#                             if agent_name and agent_name not in loaded_agent_names:
#                                 self.agents.append(agent)
#                                 loaded_agent_names.add(agent_name)
#                             else:
#                                 logger.warning(f"Skipping duplicate agent: {agent_name}")

#     def __load_triggers(self):
#         if os.path.exists(os.path.join(self.module_path, "triggers.py")):
#             module = importlib.import_module(self.module_import_path + ".triggers")
#             if hasattr(module, "triggers"):
#                 self.triggers = module.triggers

#     def __load_ontologies(self):
#         if os.path.exists(os.path.join(self.module_path, "ontologies")):
#             for file in glob.glob(
#                 os.path.join(self.module_path, "ontologies", "**", "*.ttl"),
#                 recursive=True,
#             ):
#                 self.ontologies.append(file)

#     def on_initialized(self):
#         if hasattr(self.imported_module, "on_initialized"):
#             self.imported_module.on_initialized()
#             self.imported_module.on_initialized()
