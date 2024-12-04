from abi.pipeline import Pipeline, PipelineConfiguration
from dataclasses import dataclass
from src.data.integrations import YourIntegration
from abi.utils.Graph import ABIGraph
from rdflib import Graph


from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService

from src import secret

@dataclass
class YourPipelineConfiguration(PipelineConfiguration):
    """Configuration for YourPipeline.
    
    Attributes:
        attribute_1 (str): Description of attribute_1
        attribute_2 (int): Description of attribute_2
        ontology_store_name (str): Name of the ontology store to use. Defaults to "yourstorename"
    """
    attribute_1: str
    attribute_2: int
    ontology_store_name: str = "yourstorename"

class YourPipeline(Pipeline):
    def __init__(self, integration: YourIntegration, ontology_store: IOntologyStoreService, configuration: YourPipelineConfiguration):
        super().__init__([integration], configuration)
        
        self.__integration = integration
        self.__configuration = configuration
        self.__ontology_store = ontology_store
        
    def run(self) -> Graph:        
        graph = ABIGraph()
        
        # ... Add your code here
        
        return graph
