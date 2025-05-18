from abc import ABC, abstractmethod
from abi.services.triple_store.TripleStorePorts import OntologyEvent
from lib.abi.services.agent.Agent import Agent
from typing import Callable, List, Dict, Any
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
    triggers: List[tuple[tuple[any, any, any], OntologyEvent, Callable]]
    ontologies: List[str]
    
    def __init__(self, module_path: str, module_import_path: str, imported_module: Any):
        self.module_path = module_path
        self.module_import_path = module_import_path
        self.imported_module = imported_module
        self.triggers = []
        self.ontologies = []
        self.agents = []
    
    def load(self):
        try:
            self.__load_agents()
            self.__load_triggers()
            self.__load_ontologies()
        except Exception as e:
            print(f"❌ Error loading module {self.module_import_path}: {e}")
    
    def load_agents(self):
        try:
            self.__load_agents()
        except Exception as e:
            print(f"❌ Error loading agents for module {self.module_import_path}: {e}")
    
    def __load_agents(self):
        # Load agents
        agents_path = os.path.join(self.module_path, 'agents')
        if os.path.exists(agents_path):
            for file in os.listdir(agents_path):
                if file.endswith('.py'):
                    agent_path = self.module_import_path + '.agents.' + file[:-3]
                    module = importlib.import_module(agent_path)
                    if hasattr(module, 'create_agent'):
                        self.agents.append(module.create_agent())
                    
    def __load_triggers(self):
        if os.path.exists(os.path.join(self.module_path, 'triggers.py')):
            module = importlib.import_module(self.module_import_path + '.triggers')
            if hasattr(module, 'triggers'):
                self.triggers = module.triggers

    def __load_ontologies(self):
        if os.path.exists(os.path.join(self.module_path, 'ontologies')):
            for file in glob.glob(os.path.join(self.module_path, 'ontologies', '**', '*.ttl'), recursive=True):
                self.ontologies.append(file)

    def on_initialized(self):
        if hasattr(self.imported_module, 'on_initialized'):
            self.imported_module.on_initialized()