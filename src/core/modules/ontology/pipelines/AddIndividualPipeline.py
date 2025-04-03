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

BFO = Namespace("http://purl.obolibrary.org/obo/")
CCO = Namespace("https://www.commoncoreontologies.org/")
ABI = Namespace("http://ontology.naas.ai/abi/")

@dataclass
class AddIndividualPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddIndividualPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
    """
    triple_store: ITripleStoreService

class AddIndividualPipelineParameters(PipelineParameters):
    class_uri: str = Field(..., description="Class URI to add the individual to. Please make sure the class URI is valid and exists in the ontology. Use tool `ontology_search_class` to search for a class in the ontology.")
    individual_label: str = Field(..., description="Individual label to add to the ontology.")

class AddIndividualPipeline(Pipeline):
    """Pipeline for adding a named individual."""
    __configuration: AddIndividualPipelineConfiguration
    
    def __init__(self, configuration: AddIndividualPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: AddIndividualPipelineParameters) -> Tuple[str, Graph]:
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