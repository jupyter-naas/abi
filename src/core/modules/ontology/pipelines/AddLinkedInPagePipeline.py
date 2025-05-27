from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, Annotated
from rdflib import URIRef, Literal, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
    ABI,
)
from enum import Enum

@dataclass
class AddLinkedInPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddLinkedInPagePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddLinkedInPagePipelineParameters(PipelineParameters):
    label: Annotated[Optional[str], Field(
        None,
        description="LinkedIn page URL to be added.",
        pattern="https?:\/\/.+\.linkedin\.com\/(in|company|school|showcase)\/[^?]+"
    )]
    linkedin_id: Annotated[Optional[str], Field(
        None,
        description="LinkedIn unique ID of the individual."
    )]
    linkedin_url: Annotated[Optional[str], Field(
        None,
        description="LinkedIn URL with the LinkedIn ID as identifier."
    )]
    linkedin_public_id: Annotated[Optional[str], Field(
        None,
        description="LinkedIn Public ID of the individual."
    )]
    linkedin_public_url: Annotated[Optional[str], Field(
        None,
        description="LinkedIn Public URL of the individual with the LinkedIn Public ID as identifier.",
        pattern="https?:\/\/.+\.linkedin\.com\/(in|company|school|showcase)\/[^?]+"
    )]
    owner_uri: Annotated[Optional[str], Field(
        None,
        description="URI of the owner from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443"
    )]

class AddLinkedInPagePipeline(Pipeline):
    """Pipeline for adding a new LinkedIn page to the ontology."""

    __configuration: AddLinkedInPagePipelineConfiguration

    def __init__(self, configuration: AddLinkedInPagePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AddLinkedInPagePipelineParameters):
            raise ValueError("Parameters must be of type AddLinkedInPagePipelineParameters")
        
        # Initialize graphs
        graph_insert = Graph()
        
        # Determine class URI and process LinkedIn URL components
        class_uri = ABI.LinkedInProfilePage
        if parameters.label:
            if "/in/" in parameters.label:
                identifier = "/in/"
                class_uri = ABI.LinkedInProfilePage
            elif "/company/" in parameters.label or "/showcase/" in parameters.label:
                identifier = "/company/"
                class_uri = ABI.LinkedInCompanyPage
            elif "/school/" in parameters.label:
                identifier = "/school/"
                class_uri = ABI.LinkedInSchoolPage
            
            # Extract LinkedIn Public ID and URL if not provided
            if not parameters.linkedin_public_id:
                parameters.linkedin_public_id = parameters.label.split(identifier)[-1].split('/')[0]
            if not parameters.linkedin_public_url:
                parameters.linkedin_public_url = f"https://www.linkedin.com{identifier}{parameters.linkedin_public_id}"

        # Create or get subject URI & graph
        url_to_use = parameters.linkedin_public_url or parameters.label
        individual_uri, graph = self.__add_individual_pipeline.run(
            AddIndividualPipelineParameters(
                class_uri=class_uri,
                individual_label=url_to_use
            )
        )
        individual_uri = URIRef(individual_uri)

        # Update properties
        if parameters.linkedin_id:
            check_id = list(graph.triples((individual_uri, ABI.linkedin_id, Literal(parameters.linkedin_id))))
            if len(check_id) == 0:
                graph_insert.add((individual_uri, ABI.linkedin_id, Literal(parameters.linkedin_id)))
        
        if parameters.linkedin_url:
            check_url = list(graph.triples((individual_uri, ABI.linkedin_url, Literal(parameters.linkedin_url))))
            if len(check_url) == 0:
                graph_insert.add((individual_uri, ABI.linkedin_url, Literal(parameters.linkedin_url)))
        
        if parameters.linkedin_public_id:
            check_public_id = list(graph.triples((individual_uri, ABI.linkedin_public_id, Literal(parameters.linkedin_public_id))))
            if len(check_public_id) == 0:
                graph_insert.add((individual_uri, ABI.linkedin_public_id, Literal(parameters.linkedin_public_id)))
        
        if parameters.linkedin_public_url:
            check_public_url = list(graph.triples((individual_uri, ABI.linkedin_public_url, Literal(parameters.linkedin_public_url))))
            if len(check_public_url) == 0:
                graph_insert.add((individual_uri, ABI.linkedin_public_url, Literal(parameters.linkedin_public_url)))
        
        if parameters.owner_uri:
            owner_uri = URIRef(parameters.owner_uri)
            check_owner = list(graph.triples((individual_uri, ABI.isLinkedInPageOf, owner_uri)))
            if len(check_owner) == 0:
                graph_insert.add((individual_uri, ABI.isLinkedInPageOf, owner_uri))
                graph_insert.add((owner_uri, ABI.hasLinkedInPage, individual_uri))

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph
    
    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="ontology_add_linkedin_page",
                description="Add a LinkedIn page to the ontology. Requires the LinkedIn page URL.",
                func=lambda **kwargs: self.run(
                    AddLinkedInPagePipelineParameters(**kwargs)
                ),
                args_schema=AddLinkedInPagePipelineParameters,
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
