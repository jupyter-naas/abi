from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, RDF, OWL, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters
)

@dataclass
class AddLinkedInPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddLinkedInPagePipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddLinkedInPagePipelineParameters(PipelineParameters):
    label: str = Field(..., description="LinkedIn page URL (e.g., 'https://www.linkedin.com/(in|company|school|edu)/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*')")
    individual_uri: Optional[str] = Field(None, description="URI of the individual if already known.")
    linkedin_id: Optional[str] = Field(None, description="LinkedIn unique ID of the individual. It must starts with 'ACoAAA'")
    linkedin_url: Optional[str] = Field(None, description="LinkedIn URL with the LinkedIn ID as identifier. It must starts with 'https://www.linkedin.com/in/ACoAAA'")
    linkedin_public_id: Optional[str] = Field(None, description="LinkedIn Public ID of the individual.")
    linkedin_public_url: Optional[str] = Field(None, description="LinkedIn Public URL of the individual with the LinkedIn Public ID as identifier. It must starts with 'https://www.linkedin.com/in/'")
    owner_uris: Optional[List[str]] = Field(None, description="URIs of the owner of the LinkedIn page. It can be a Person URI from class: https://www.commoncoreontologies.org/ont00001262 or a Organization URI from subclass of: https://www.commoncoreontologies.org/ont00001180")

class AddLinkedInPagePipeline(Pipeline):
    """Pipeline for adding a new LinkedIn page to the ontology."""
    __configuration: AddLinkedInPagePipelineConfiguration
    
    def __init__(self, configuration: AddLinkedInPagePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddLinkedInPagePipelineParameters) -> str:
        # Get class URI
        if "/in/" in parameters.url:
            identifier = "/in/"
            class_uri = ABI.LinkedInProfilePage
        elif "/company/" in parameters.url:
            identifier = "/company/"
            class_uri = ABI.LinkedInCompanyPage
        elif "/school/" in parameters.url:
            identifier = "/school/"
            class_uri = ABI.LinkedInSchoolPage
        else:
            raise ValueError("Invalid LinkedIn URL")
        
        # Create LinkedIn page URI
        linkedin_page_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
            class_uri=class_uri,
            individual_label=parameters.label
        ))

        # Add LinkedIn Public ID if provided
        linkedin_public_id = parameters.linkedin_public_id
        if not linkedin_public_id:
            linkedin_public_id = parameters.label.split(identifier)[-1].split('/')[0]
        graph.add((linkedin_page_uri, ABI.linkedin_public_id, Literal(linkedin_public_id)))

        # Add LinkedIn Public URL if provided
        linkedin_public_url = parameters.linkedin_public_url
        if not linkedin_public_url:
            linkedin_public_url = "https://www.linkedin.com" + identifier + linkedin_public_id
        graph.add((linkedin_page_uri, ABI.linkedin_public_url, Literal(linkedin_public_url)))
        
        # Add LinkedIn ID if provided
        if parameters.linkedin_id:
            graph.add((linkedin_page_uri, ABI.linkedin_id, Literal(parameters.linkedin_id)))
            
        # Add LinkedIn URL if provided
        if parameters.linkedin_url:
            graph.add((linkedin_page_uri, ABI.linkedin_url, Literal(parameters.linkedin_url)))

        # Add owners URI if provided
        if parameters.owner_uris:
            for owner_uri in parameters.owner_uris:
                graph.add((linkedin_page_uri, ABI.isLinkedInPageOf, URIRef(owner_uri)))
                graph.add((URIRef(owner_uri), ABI.hasLinkedInPage, linkedin_page_uri))
            
        return linkedin_page_uri
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_linkedin_page",
                description="Add a LinkedIn page to the ontology. Requires the LinkedIn page URL.",
                func=lambda **kwargs: self.run(AddLinkedInPagePipelineParameters(**kwargs)),
                args_schema=AddLinkedInPagePipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 