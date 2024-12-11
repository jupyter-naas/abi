from abc import abstractmethod
from abi.integration import Integration
from abi.utils.Expose import Expose
from rdflib import Graph
from abi.utils.Expose import Expose
from pydantic import BaseModel
from dataclasses import dataclass

@dataclass
class PipelineConfiguration():
    """Base configuration class for pipelines.
    
    This class serves as the base configuration for all pipeline classes.
    Concrete pipeline implementations should extend this class and add their
    specific configuration attributes.
    """
    pass

class PipelineParameters(BaseModel):
    """Base parameters class for pipeline execution.
    
    This class serves as the base parameters for all pipeline executions.
    Concrete pipeline implementations should extend this class and add their
    specific runtime parameters.
    """

    pass

class Pipeline(Expose):
    __configuration: PipelineConfiguration
    
    def __init__(self, configuration: PipelineConfiguration):
        self.__configuration = configuration

    @abstractmethod
    def run(self, parameters : PipelineParameters) -> Graph:
        """Execute the pipeline with the given parameters.
        
        This method should be implemented by concrete pipeline classes to process data
        according to their specific logic and configuration.
        
        Args:
            parameters (PipelineParameters): Runtime parameters for pipeline execution
                that control how the pipeline processes data
                
        Returns:
            Graph: An RDF graph containing the processed data and relationships
            
        Raises:
            NotImplementedError: If the concrete class does not implement this method
        """
        raise NotImplementedError()