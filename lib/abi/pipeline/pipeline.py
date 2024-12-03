from abc import abstractmethod
from dataclasses import dataclass
from abi.integration import Integration
from rdflib import Graph


@dataclass
class PipelineConfiguration:
    pass

class Pipeline:
    __integrations: list[Integration]
    __configuration: PipelineConfiguration
    
    def __init__(self, integrations: list[Integration], configuration: PipelineConfiguration):
        self.__integrations = integrations
        self.__configuration = configuration

    @abstractmethod
    def run(self) -> Graph:
        """Execute the pipeline's logic.
        
        This method should be implemented by concrete pipeline classes to define their specific
        data processing and transformation logic.
        
        Returns:
            Graph: An RDF graph containing the pipeline's output data
        
        Raises:
            NotImplementedError: If the concrete class does not implement this method
        """
        raise NotImplementedError()