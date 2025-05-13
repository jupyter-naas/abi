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
    AddIndividualPipelineParameters,
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
    name: Optional[str] = Field(
        None,
        description="Name of the commercial organization to be added in class: https://www.commoncoreontologies.org/ont00000443",
    )
    individual_uri: Optional[str] = Field(
        None,
        description="URI of the commercial organization if already known. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    legal_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: https://www.commoncoreontologies.org/ont00001331. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    ticker_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: http://ontology.naas.ai/abi/Ticker. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    website_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: http://ontology.naas.ai/abi/Website. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    linkedin_page_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: http://ontology.naas.ai/abi/LinkedInOrganizationPage. It must start with 'http://ontology.naas.ai/abi/'.",
    )


class AddCommercialOrganizationPipeline(Pipeline):
    """Pipeline for adding a new commercial organization to the ontology."""

    __configuration: AddCommercialOrganizationPipelineConfiguration

    def __init__(self, configuration: AddCommercialOrganizationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddCommercialOrganizationPipelineParameters) -> str:
        # Initialize a new graph
        graph = Graph()

        # Create organization URI using name
        organization_uri = parameters.individual_uri
        if parameters.name and not organization_uri:
            # Create organization URI using name
            organization_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=CCO.ont00000443, individual_label=parameters.name
                )
            )
        else:
            if organization_uri.startswith("http://ontology.naas.ai/abi/"):
                organization_uri = URIRef(organization_uri)
            else:
                raise ValueError(
                    f"Invalid Organization URI: {organization_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add legal URI if provided
        if parameters.legal_uri:
            if parameters.legal_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (organization_uri, ABI.hasLegalName, URIRef(parameters.legal_uri))
                )
                graph.add(
                    (URIRef(parameters.legal_uri), ABI.isLegalNameOf, organization_uri)
                )
            else:
                raise ValueError(
                    f"Invalid Legal URI: {parameters.legal_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add website URL if provided
        if parameters.website_uri:
            if parameters.website_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (organization_uri, ABI.hasWebsite, URIRef(parameters.website_uri))
                )
                graph.add(
                    (URIRef(parameters.website_uri), ABI.isWebsiteOf, organization_uri)
                )
            else:
                raise ValueError(
                    f"Invalid Website URI: {parameters.website_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add ticker URI if provided
        if parameters.ticker_uri:
            if parameters.ticker_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (
                        organization_uri,
                        ABI.hasTickerSymbol,
                        URIRef(parameters.ticker_uri),
                    )
                )
                graph.add(
                    (
                        URIRef(parameters.ticker_uri),
                        ABI.isTickerSymbolOf,
                        organization_uri,
                    )
                )
            else:
                raise ValueError(
                    f"Invalid Ticker URI: {parameters.ticker_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Add LinkedIn page URI if provided
        if parameters.linkedin_page_uri:
            if parameters.linkedin_page_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (
                        organization_uri,
                        ABI.hasLinkedInPage,
                        URIRef(parameters.linkedin_page_uri),
                    )
                )
                graph.add(
                    (
                        URIRef(parameters.linkedin_page_uri),
                        ABI.isLinkedInPageOf,
                        organization_uri,
                    )
                )
            else:
                raise ValueError(
                    f"Invalid LinkedIn Page URI: {parameters.linkedin_page_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return organization_uri

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_commercial_organization",
                description="Add a commercial organization with a name and optional website URL to the ontology. Use your internal knowledge to find the website URL.",
                func=lambda **kwargs: self.run(
                    AddCommercialOrganizationPipelineParameters(**kwargs)
                ),
                args_schema=AddCommercialOrganizationPipelineParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
