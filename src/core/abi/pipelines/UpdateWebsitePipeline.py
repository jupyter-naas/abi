from dataclasses import dataclass
from typing import Optional
from pydantic import Field
from rdflib import Graph, URIRef
from abi.utils.Graph import ABI, URI_REGEX
from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from langchain_core.tools import StructuredTool, BaseTool
from typing import Annotated
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from fastapi import APIRouter
from enum import Enum


@dataclass
class UpdateWebsitePipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdateWebsitePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService

class UpdateWebsitePipelineParameters(PipelineParameters):
    individual_uri: Annotated[str, Field(
        description="URI of the website. It must start with 'http://ontology.naas.ai/abi/'.",
        pattern=URI_REGEX
    )]
    owner_uri: Annotated[Optional[str], Field(
        None,
        description="Owner URI from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443.",
        pattern=URI_REGEX
    )] = None

class UpdateWebsitePipeline(Pipeline):
    """Pipeline for updating a Website in the ontology."""

    __configuration: UpdateWebsitePipelineConfiguration

    def __init__(self, configuration: UpdateWebsitePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateWebsitePipelineParameters):
            raise ValueError("Parameters must be of type UpdateWebsitePipelineParameters")
        
        # Initialize a new graph
        graph = Graph()
        
        # Get website URI
        website_uri = URIRef(parameters.individual_uri)
        if not parameters.individual_uri.startswith("http://ontology.naas.ai/abi/"):
            raise ValueError(
                f"Invalid Website URI: {parameters.individual_uri}. It must start with 'http://ontology.naas.ai/abi/'."
            )

        # Add owners URI if provided
        if parameters.owner_uri:
            check_owner_uri = list(graph.triples((website_uri, ABI.isWebsiteOf, URIRef(parameters.owner_uri))))
            if len(check_owner_uri) == 0:
                graph.add((website_uri, ABI.isWebsiteOf, URIRef(parameters.owner_uri)))
                graph.add((URIRef(parameters.owner_uri), ABI.hasWebsite, website_uri))

        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_website",
                description="Update a website in the ontology.",
                func=lambda **kwargs: self.run(UpdateWebsitePipelineParameters(**kwargs)),
                args_schema=UpdateWebsitePipelineParameters,
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
