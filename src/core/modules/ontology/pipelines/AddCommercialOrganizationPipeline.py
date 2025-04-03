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
class AddCommercialOrganizationPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddCommercialOrganizationPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddCommercialOrganizationPipelineParameters(PipelineParameters):
    name: str = Field(..., description="Name of the commercial organization")
    website_url: Optional[str] = Field(None, description="Website URL of the organization (e.g., 'https://www.example.com')")

class AddCommercialOrganizationPipeline(Pipeline):
    """Pipeline for adding a new commercial organization to the ontology."""
    __configuration: AddCommercialOrganizationPipelineConfiguration
    
    def __init__(self, configuration: AddCommercialOrganizationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddCommercialOrganizationPipelineParameters) -> Graph:
        # Create organization URI using name
        organization_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
            class_uri=CCO.ont00000443,
            individual_label=parameters.name
        ))

        # Initialize a new graph for performance
        graph = Graph()

        # Add website URL if provided
        if parameters.website_url:
            graph.add((organization_uri, ABI.website_url, Literal(parameters.website_url)))
        
        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_commercial_organization",
                description="Add a commercial organization with a name and optional website URL to the ontology. Use your internal knowledge to find the website URL.",
                func=lambda **kwargs: self.run(AddCommercialOrganizationPipelineParameters(**kwargs)),
                args_schema=AddCommercialOrganizationPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 