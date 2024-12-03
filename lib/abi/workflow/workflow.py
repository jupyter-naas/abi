from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class WorkflowConfiguration:
    pass

class Workflow(ABC):
    
    __configuration: WorkflowConfiguration
    
    def __init__(self, configuration: WorkflowConfiguration):
        self.__configuration = configuration
        
    def run(self):
        pass
    
    # @staticmethod
    # @abstractmethod
    # def as_api():
    #     pass
    
    # @staticmethod
    # @abstractmethod
    # def as_tool():
    #     pass
    
    # @staticmethod
    # @abstractmethod
    # def as_standalone():
    #     pass
    
    