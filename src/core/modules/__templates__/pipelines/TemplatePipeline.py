from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from src.core.modules.__templates__.integrations.TemplateIntegration import (
    YourIntegration,
    YourIntegrationConfiguration
)
from rdflib import Graph, Namespace
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from fastapi import APIRouter
from langchain_core.tools import StructuredTool, BaseTool
from enum import Enum
import uuid

ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class YourPipelineConfiguration(PipelineConfiguration):
    """Configuration for YourPipeline.
    
    Attributes:
        integration (YourIntegration): The integration instance to use
        triple_store (ITripleStoreService): The ontology store service to use
        triple_store_name (str): Name of the ontology store to use. Defaults to "yourstorename"
    """
    integration_configuration: YourIntegrationConfiguration
    triple_store: ITripleStoreService
    datastore_path: str = "datastore/__templates__"

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
        self.__integration = YourIntegration(configuration.integration_configuration)

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, YourPipelineParameters):
            raise ValueError("Parameters must be of type YourPipelineParameters")
        
        # Init graph
        graph = Graph()
        
        # Use the integration to fetch data
        raw_data = self.__integration.example_method(parameters.parameter_1)

        # URI
        uri = ABI[str(uuid.uuid4())]
        
        # Transform the raw data into semantic triples
        for item in raw_data:
            graph.add((uri, ABI.hasName, item['name']))
        
        # Store the graph in the ontology store
        self.__configuration.triple_store.insert(graph)
        
        return graph
    
    def as_tools(self) -> list[BaseTool]:
        """Returns a list of LangChain tools for this pipeline.
        
        Returns:
            list[BaseTool]: List containing the pipeline tool
        """
        return [
            StructuredTool(
                name="your_pipeline",
                description="Executes the pipeline with the given parameters",
                func=lambda **kwargs: self.run(YourPipelineParameters(**kwargs)),
                args_schema=YourPipelineParameters
            )
        ]

    def as_api(
        self,
        router: APIRouter,
        route_name: str = "",
        name: str = "",
        description: str = "",
        description_stream: str = "",
        tags: list[str | Enum] | None = None,
    ) -> None:
        if tags is None:
            tags = []
        return None