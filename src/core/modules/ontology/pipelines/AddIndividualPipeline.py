from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, Any
from abi.utils.Graph import ABIGraph, ABI
from rdflib import Graph, RDF, OWL, RDFS, URIRef, Literal
import uuid

@dataclass
class AddIndividualPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddIndividualPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
    """
    triple_store: ITripleStoreService

class AddIndividualPipelineParameters(PipelineParameters):
    class_uri: str = Field(..., description="Class URI to add the individual to. Please make sure the class URI is valid and exists in the ontology. Use tool `ontology_search_class` to search for a class in the ontology.")
    class_label: str = Field(..., description="Class label to add the individual to. Please make sure the class label is valid and exists in the ontology. Use tool `ontology_search_class` to search for a class in the ontology.")
    individual_label: str = Field(..., description="Individual label to add to the ontology.")

class AddIndividualPipeline(Pipeline):
    """Pipeline for adding a named individual."""
    __configuration: AddIndividualPipelineConfiguration
    
    def __init__(self, configuration: AddIndividualPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: AddIndividualPipelineParameters) -> Graph:
        # Init ontology graph
        ontology_name = f"{parameters.class_label.lower().replace(' ', '_')}_{parameters.class_uri.split('/')[-1]}"
        logger.info(f"Ontology name: {ontology_name}")
        graph = ABIGraph()
        try:
            graph = self.__configuration.triple_store.get(ontology_name)
        except Exception as e:
            logger.info(f"Error getting ontology graph: {e}")

        # Add individual
        individual_uri = ABI[str(uuid.uuid4())]
        graph.add((individual_uri, RDF.type, OWL.NamedIndividual))
        graph.add((individual_uri, RDF.type, URIRef(parameters.class_uri)))
        graph.add((individual_uri, RDFS.label, Literal(parameters.individual_label)))
        self.__configuration.triple_store.insert(ontology_name, graph)
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_individual",
                description="Add a new individual to an ontology if it does not already exist.",
                func=lambda **kwargs: self.run(AddIndividualPipelineParameters(**kwargs)),
                args_schema=AddIndividualPipelineParameters
            )
        ]

    def as_api(self) -> None:
        pass