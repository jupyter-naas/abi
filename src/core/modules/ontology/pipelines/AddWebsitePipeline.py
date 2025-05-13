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
    AddIndividualPipelineParameters,
)


@dataclass
class AddWebsitePipelineConfiguration(PipelineConfiguration):
    """Configuration for AddWebsitePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration


class AddWebsitePipelineParameters(PipelineParameters):
    label: str = Field(
        ...,
        description="Website URL (e.g., 'https://www.example.com') to be added in class: http://ontology.naas.ai/abi/Website",
    )
    individual_uri: Optional[str] = Field(
        None,
        description="URI of the individual if already known. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    owner_uris: Optional[List[str]] = Field(
        None,
        description="Owners URI from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443",
    )


class AddWebsitePipeline(Pipeline):
    """Pipeline for adding a new Website to the ontology."""

    __configuration: AddWebsitePipelineConfiguration

    def __init__(self, configuration: AddWebsitePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddWebsitePipelineParameters) -> str:
        # Initialize a new graph
        graph = Graph()

        # Create Website URI
        website_uri = parameters.individual_uri
        if parameters.label and not website_uri:
            website_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=ABI.Website, individual_label=parameters.label
                )
            )
        else:
            if website_uri.startswith("http://ontology.naas.ai/abi/"):
                website_uri = URIRef(website_uri)
            else:
                raise ValueError(
                    f"Invalid Website URI: {website_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add owners URI if provided
        if parameters.owner_uris:
            for owner_uri in parameters.owner_uris:
                if owner_uri.startswith("http://ontology.naas.ai/abi/"):
                    graph.add((website_uri, ABI.isWebsiteOf, URIRef(owner_uri)))
                    graph.add((URIRef(owner_uri), ABI.hasWebsite, website_uri))
                else:
                    raise ValueError(
                        f"Invalid Owner URI: {owner_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                    )

        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return website_uri

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_website",
                description="Add a website to the ontology. Requires the website URL.",
                func=lambda **kwargs: self.run(AddWebsitePipelineParameters(**kwargs)),
                args_schema=AddWebsitePipelineParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
