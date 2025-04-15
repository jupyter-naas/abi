from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, Any, Tuple
from rdflib import Graph, URIRef, Literal, Namespace, RDF, OWL, RDFS, SKOS, XSD, TIME, DCTERMS
import uuid
from src.core.modules.ontology.workflows.SearchIndividualWorkflow import SearchIndividualWorkflow, SearchIndividualWorkflowParameters, SearchIndividualWorkflowConfiguration

BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class AddIndividualPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddIndividualPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
        search_individual_workflow (SearchIndividualWorkflow): The search individual workflow to use
    """
    triple_store: ITripleStoreService
    search_individual_configuration: SearchIndividualWorkflowConfiguration

class AddIndividualPipelineParameters(PipelineParameters):
    class_uri: str = Field(
        ..., 
        description="Class URI to add the individual to. Use tool `ontology_search_class` to search for a class URI in the ontology.",
        pattern="https?:\/\/.*",
        example="https://www.commoncoreontologies.org/ont00000443"
    )
    individual_label: str = Field(
        ..., 
        description="Individual label to add to the ontology.",
        example="Naas.ai"
    )

class AddIndividualPipeline(Pipeline):
    """Pipeline for adding a named individual."""
    __configuration: AddIndividualPipelineConfiguration
    
    def __init__(self, configuration: AddIndividualPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__search_individual_workflow = SearchIndividualWorkflow(configuration.search_individual_configuration)

    def run(self, parameters: AddIndividualPipelineParameters) -> Tuple[str, Graph]:
        # Search for individual
        search_individual_result = self.__search_individual_workflow.search_individual(SearchIndividualWorkflowParameters(
            class_uri=parameters.class_uri,
            search_label=parameters.individual_label
        ))
        if len(search_individual_result) > 0:
            score = int(search_individual_result[0]['score'])
            if score > 8:
                individual_uri = search_individual_result[0]['individual_uri']
                logger.debug(f"🔍 Found individual '{parameters.individual_label}' in the ontology: {individual_uri} from class: {parameters.class_uri}")
                return URIRef(individual_uri), self.__configuration.triple_store.get_subject_graph(individual_uri)
        
        # Init graph
        graph = Graph()
        graph.bind("bfo", BFO)
        graph.bind("cco", CCO)
        graph.bind("abi", ABI)
        graph.bind("dcterms", DCTERMS)

        # Add individual
        individual_uri = ABI[str(uuid.uuid4())]
        graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        graph.add((individual_uri, RDF.type, URIRef(parameters.class_uri)))
        graph.add((individual_uri, RDFS.label, Literal(parameters.individual_label)))
        self.__configuration.triple_store.insert(graph)
        logger.debug(f"✅ Added individual '{parameters.individual_label}' to the ontology: {individual_uri} from class: {parameters.class_uri}")
        return individual_uri, graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_individual",
                description="Add a new individual/instance to triple store.",
                func=lambda **kwargs: self.run(AddIndividualPipelineParameters(**kwargs)),
                args_schema=AddIndividualPipelineParameters
            )
        ]

    def as_api(self) -> None:
        pass