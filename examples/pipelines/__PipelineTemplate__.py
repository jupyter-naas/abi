from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.data.integrations import YourIntegration
from abi.utils.Graph import ABIGraph
from rdflib import Graph
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from abi import logger
from src import config, secret
from fastapi import APIRouter
from langchain_core.tools import StructuredTool

@dataclass
class YourPipelineConfiguration(PipelineConfiguration):
    """Configuration for YourPipeline.
    
    Attributes:
        integration (YourIntegration): The integration instance to use
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "yourstorename"
    """
    integration: YourIntegration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "yourstorename"

class YourPipelineParameters(PipelineParameters):
    """Parameters for YourPipeline execution.
    
    Attributes:
        parameter_1 (str): Description of parameter_1
        parameter_2 (int): Description of parameter_2
    """
    parameter_1: str
    parameter_2: int

class YourPipeline(Pipeline):
    __configuration: YourPipelineConfiguration
    
    def __init__(self, configuration: YourPipelineConfiguration):
        self.__configuration = configuration

    def run(self, parameters: YourPipelineParameters) -> Graph:        
        graph = ABIGraph()
        
        # ... Add your code here
        
        self.__configuration.ontology_store.insert(self.__configuration.ontology_store_name, graph)
        return graph
        
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[StructuredTool]: List containing the pipeline tool
        """
        return [StructuredTool(
            name="your_pipeline",
            description="Executes the pipeline with the given parameters",
            func=lambda **kwargs: self.run(YourPipelineParameters(**kwargs)),
            args_schema=YourPipelineParameters
        )]

    def as_api(self, router: APIRouter) -> None:
        """Adds API endpoints for this pipeline to the given router.
        
        Args:
            router (APIRouter): FastAPI router to add endpoints to
        """
        @router.post("/YourPipeline")
        def run(parameters: YourPipelineParameters):
            return self.run(parameters).serialize(format="turtle")
        
if __name__ == "__main__":
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    from abi.services.ontology_store.OntologyStoreService import OntologyStoreService
    from src.core.modules.common.integrations import YourIntegration, YourIntegrationConfiguration
    
    # Init store
    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))

    # Initialize integration
    integration = YourIntegration(YourIntegrationConfiguration(attribute_1=secret.get("YOUR_SECRET_1"), attribute_2=secret.get("YOUR_SECRET_2")))
                    
    # Initialize configuration  
    configuration = YourPipelineConfiguration(
        integration=integration,
        ontology_store=ontology_store,
        ontology_store_name="yourstorename"
    )
    
    # Initialize pipeline
    pipeline = YourPipeline(configuration)
    
    # Run pipeline
    result = pipeline.run(YourPipelineParameters(parameter_1="value1", parameter_2=123))


