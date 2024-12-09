from dataclasses import dataclass
from abc import ABC, abstractmethod


@dataclass
class WorkflowConfiguration:
    pass

class Workflow(ABC):
    """A workflow represents a sequence of operations that can be exposed in multiple ways.
    
    Workflows encapsulate business logic that can be:
    - Scheduled as background jobs
    - Exposed as tools for AI agents
    - Served via API endpoints
    - Run directly as Python code
    
    The workflow pattern provides a consistent way to package functionality
    that needs to be accessible through multiple interfaces.
    
    Attributes:
        __configuration (WorkflowConfiguration): Configuration parameters for the workflow
        
    Example:
        >>> config = MyWorkflowConfig(param1="value1")
        >>> workflow = MyWorkflow(config)
        >>> result = workflow.run()
    """
    
    __configuration: WorkflowConfiguration
    
    def __init__(self, configuration: WorkflowConfiguration):
        self.__configuration = configuration
        
    def run(self):
        pass
