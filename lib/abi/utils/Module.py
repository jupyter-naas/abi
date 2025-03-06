from abc import ABC, abstractmethod
from lib.abi.services.agent.Agent import Agent
from typing import List, Dict, Any
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
    
    def __init__(self, module_path: str, module_import_path: str):
        self.module_path = module_path
        self.module_import_path = module_import_path
        
        self.agents = []
    
    def load(self):
        self.__load_agents()
        
    
    def __load_agents(self):
        # Check if assistants directory exists and load agents from there
        assistants_path = os.path.join(self.module_path, 'assistants')
        if os.path.exists(assistants_path) and os.path.isdir(assistants_path):
            for file in os.listdir(assistants_path):
                if file.endswith('.py'):
                    assistant_path = self.module_import_path + '.assistants.' + file[:-3]
                    module = importlib.import_module(assistant_path)
                    if hasattr(module, 'create_agent'):
                        self.agents.append(module.create_agent())

        # Also check if agent directory exists and load agents from there
        agent_path = os.path.join(self.module_path, 'agent')
        if os.path.exists(agent_path) and os.path.isdir(agent_path):
            for file in os.listdir(agent_path):
                if file.endswith('.py'):
                    agent_module_path = self.module_import_path + '.agent.' + file[:-3]
                    module = importlib.import_module(agent_module_path)
                    if hasattr(module, 'create_agent'):
                        self.agents.append(module.create_agent())
                    # Additionally check for create_hr_agent or other specific creation functions
                    elif hasattr(module, 'create_hr_agent'):
                        self.agents.append(module.create_hr_agent())