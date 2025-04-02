from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import Optional
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, RDF, OWL, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters
)

@dataclass
class AddPersonPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddPersonPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddPersonPipelineParameters(PipelineParameters):
    name: str = Field(..., description="Person's name. It must have a first name and a last name.")
    first_name: Optional[str] = Field(None, description="Person's first name")
    last_name: Optional[str] = Field(None, description="Person's last name")

class AddPersonPipeline(Pipeline):
    """Pipeline for adding a new person to the ontology."""
    __configuration: AddPersonPipelineConfiguration
    
    def __init__(self, configuration: AddPersonPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddPersonPipelineParameters) -> Graph:
        # Create person URI using first and last name
        person_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
            class_uri=CCO.ont00001262,
            individual_label=parameters.name
        ))

        # Add person type and properties
        if parameters.first_name:
            graph.add((person_uri, ABI.firstName, Literal(parameters.first_name)))
        if parameters.last_name:
            graph.add((person_uri, ABI.lastName, Literal(parameters.last_name)))
        
        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return person_uri, graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_person",
                description="Adds a new person to the ontology with first name and last name. Returns the person's graph.",
                func=lambda **kwargs: self.run(AddPersonPipelineParameters(**kwargs)),
                args_schema=AddPersonPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 