from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from langchain.tools import BaseTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional
from abi.utils.Graph import ABI
from rdflib import URIRef, Literal, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
)

URI_REGEX = r"http:\/\/ontology\.naas\.ai\/abi\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"

@dataclass
class AddLinkedInPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddLinkedInPagePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddLinkedInPagePipelineParameters(PipelineParameters):
    label: Optional[str] = Field(None, description="LinkedIn page URL to be added.", pattern="https?:\/\/.+\.linkedin\.com\/(in|company|school|showcase)\/[^?]+")
    individual_uri: Optional[str] = Field(None, description="URI of the individual if already known.", pattern=URI_REGEX)
    linkedin_id: Optional[str] = Field(None, description="LinkedIn unique ID of the individual.")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL with the LinkedIn ID as identifier.")
    linkedin_public_id: Optional[str] = Field(None, description="LinkedIn Public ID of the individual.")
    linkedin_public_url: Optional[str] = Field(None, description="LinkedIn Public URL of the individual with the LinkedIn Public ID as identifier.", pattern="https?:\/\/.+\.linkedin\.com\/(in|company|school|showcase)\/[^?]+")
    owner_uri: Optional[str] = Field(None, description="URI of the owner from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443")

class AddLinkedInPagePipeline(Pipeline):
    """Pipeline for adding a new LinkedIn page to the ontology."""

    __configuration: AddLinkedInPagePipelineConfiguration

    def __init__(self, configuration: AddLinkedInPagePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddLinkedInPagePipelineParameters) -> Graph:
        # Initialize graphs
        graph_insert = Graph()
        graph_remove = Graph()

        # Get class URI based on LinkedIn URL type
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
            
            # Get LinkedIn Public ID from URL if not provided
            linkedin_public_id = parameters.linkedin_public_id
            if not linkedin_public_id:
                linkedin_public_id = parameters.label.split(identifier)[-1].split('/')[0]

            # Get LinkedIn Public URL if not provided
            linkedin_public_url = parameters.linkedin_public_url
            if not linkedin_public_url:
                linkedin_public_url = "https://www.linkedin.com" + identifier + linkedin_public_id
        
        # Create or get subject URI & graph
        if parameters.label and not parameters.individual_uri:
            if not linkedin_public_url:
                linkedin_public_url = parameters.label
            individual_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
                class_uri=class_uri,
                individual_label=linkedin_public_url
            ))
        else:
            individual_uri = URIRef(individual_uri)
            graph = self.__configuration.triple_store.get_subject_graph(individual_uri)
        
        # Update existing objects
        linkedin_id_exists = False
        linkedin_url_exists = False
        linkedin_public_id_exists = False
        linkedin_public_url_exists = False
        owner_uri_exists = False
        for s, p, o in graph:
            if str(p) == "http://ontology.naas.ai/abi/linkedin_id":
                linkedin_id_exists = True
                if parameters.linkedin_id is not None and str(o) != parameters.linkedin_id:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.linkedin_id)))
            elif str(p) == "http://ontology.naas.ai/abi/linkedin_url":
                linkedin_url_exists = True
                if parameters.linkedin_url is not None and str(o) != parameters.linkedin_url:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.linkedin_url)))
            elif str(p) == "http://ontology.naas.ai/abi/linkedin_public_id":
                linkedin_public_id_exists = True
                if 'linkedin_public_id' in locals() and linkedin_public_id and str(o) != linkedin_public_id:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(linkedin_public_id)))
            elif str(p) == "http://ontology.naas.ai/abi/linkedin_public_url":
                linkedin_public_url_exists = True
                if 'linkedin_public_url' in locals() and linkedin_public_url and str(o) != linkedin_public_url:
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(linkedin_public_url)))
            elif str(p) == "http://ontology.naas.ai/abi/isLinkedInPageOf":
                owner_uri_exists = True
                if parameters.owner_uri is not None and str(o) != parameters.owner_uri:
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, ABI.hasLinkedInPage, s))
                    graph_insert.add((s, ABI.isLinkedInPageOf, URIRef(parameters.owner_uri)))
                    graph_insert.add((URIRef(parameters.owner_uri), ABI.hasLinkedInPage, s))

        # Add new objects
        if parameters.linkedin_id and not linkedin_id_exists:
            graph_insert.add((URIRef(individual_uri), URIRef(ABI.linkedin_id), Literal(parameters.linkedin_id)))
        if parameters.linkedin_url and not linkedin_url_exists:
            graph_insert.add((URIRef(individual_uri), URIRef(ABI.linkedin_url), Literal(parameters.linkedin_url)))
        if parameters.linkedin_public_id and not linkedin_public_id_exists:
            graph_insert.add((URIRef(individual_uri), URIRef(ABI.linkedin_public_id), Literal(parameters.linkedin_public_id)))
        if parameters.linkedin_public_url and not linkedin_public_url_exists:
            graph_insert.add((URIRef(individual_uri), URIRef(ABI.linkedin_public_url), Literal(parameters.linkedin_public_url)))
        if parameters.owner_uri and not owner_uri_exists:
            graph_insert.add((URIRef(individual_uri), URIRef(ABI.isLinkedInPageOf), URIRef(parameters.owner_uri)))
            graph_insert.add((URIRef(parameters.owner_uri), URIRef(ABI.hasLinkedInPage), URIRef(individual_uri)))

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        self.__configuration.triple_store.remove(graph_remove)
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

    def as_api(self, router: Optional[APIRouter] = None) -> None:
        pass
