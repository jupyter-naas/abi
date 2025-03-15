from abc import ABC, abstractmethod
from abi.services.ontology_store.OntologyStorePorts import OntologyEvent
from lib.abi.services.agent.Agent import Agent
from typing import Callable, List, Dict, Any
import os
import importlib

class IModule(ABC):
    """Base interface class for ABI modules.
    
    This class serves as the base interface for all modules in the src/modules directory.
    
    The IModule class provides a default loading mechanism.
    
    
    The default loading mechanism will:
    1. Load all agents from the module's 'assistants' directory
    2. Initialize module configuration and state
    
    Attributes:
        agents (List[Agent]): List of agents loaded from the module
    """
    
    agents: List[Agent]
    triggers: List[tuple[tuple[any, any, any], OntologyEvent, Callable]]
    
    def __init__(self, module_path: str, module_import_path: str):
        self.module_path = module_path
        self.module_import_path = module_import_path
        self.triggers = []
        
        self.agents = []
    
    def load(self):
        self.__load_agents()
        self.__load_triggers()
    
    
    
    def __load_agents(self):
        for file in os.listdir(os.path.join(self.module_path, 'assistants')):
            if file.endswith('.py'):
                assistant_path = self.module_import_path + '.assistants.' + file[:-3]
                module = importlib.import_module(assistant_path)
                if hasattr(module, 'create_agent'):
                    self.agents.append(module.create_agent())
                    
    def __load_triggers(self):
        if os.path.exists(os.path.join(self.module_path, 'triggers.py')):
            module = importlib.import_module(self.module_import_path + '.triggers')
            if hasattr(module, 'triggers'):
                self.triggers = module.triggers
