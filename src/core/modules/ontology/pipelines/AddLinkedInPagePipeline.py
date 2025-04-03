from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
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
class AddLinkedInPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddLinkedInPagePipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddLinkedInPagePipelineParameters(PipelineParameters):
    url: str = Field(..., description="LinkedIn page URL (e.g., 'https://www.linkedin.com/(in|company|school|edu)/[a-zA-Z0-9_-]+(?:/[a-zA-Z0-9_-]+)*')")

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
            class_uri = ABI.LinkedInProfilePage
        elif "/company/" in parameters.url:
            class_uri = ABI.LinkedInCompanyPage
        elif "/school/" in parameters.url:
            class_uri = ABI.LinkedInSchoolPage
        else:
            raise ValueError("Invalid LinkedIn URL")
        
        # Create LinkedIn page URI
        linkedin_page_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
            class_uri=class_uri,
            individual_label=parameters.url
        ))
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