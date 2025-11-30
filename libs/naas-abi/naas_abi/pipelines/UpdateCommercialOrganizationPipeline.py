from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from fastapi import APIRouter
from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Graph import ABI, URI_REGEX
from pydantic import Field
from rdflib import Graph, Literal, URIRef


@dataclass
class UpdateCommercialOrganizationPipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdateCommercialOrganizationPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService


class UpdateCommercialOrganizationPipelineParameters(PipelineParameters):
    individual_uri: Annotated[
        str,
        Field(
            description="URI of the commercial organization extracted from class: https://www.commercoreontologies.org/ont00000443",
            pattern=URI_REGEX,
        ),
    ]
    legal_uri: Annotated[
        Optional[str],
        Field(
            description="Individual URI from class: https://www.commoncoreontologies.org/ont00001331",
            pattern=URI_REGEX,
        ),
    ] = None
    ticker_uri: Annotated[
        Optional[str],
        Field(
            description="Individual URI from class: http://ontology.naas.ai/abi/Ticker",
            pattern=URI_REGEX,
        ),
    ] = None
    website_uri: Annotated[
        Optional[str],
        Field(
            description="Individual URI from class: http://ontology.naas.ai/abi/Website",
            pattern=URI_REGEX,
        ),
    ] = None
    linkedin_page_uri: Annotated[
        Optional[str],
        Field(
            description="Individual URI from class: http://ontology.naas.ai/abi/LinkedInOrganizationPage",
            pattern=URI_REGEX,
        ),
    ] = None
    logo_url: Annotated[
        Optional[str],
        Field(
            description="Logo URL of the commercial organization.",
            pattern=r"https?://.*",
        ),
    ] = None


class UpdateCommercialOrganizationPipeline(Pipeline):
    """Pipeline for updating a commercial organization in the ontology."""

    __configuration: UpdateCommercialOrganizationPipelineConfiguration

    def __init__(
        self, configuration: UpdateCommercialOrganizationPipelineConfiguration
    ):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateCommercialOrganizationPipelineParameters):
            raise ValueError(
                "Parameters must be of type UpdateCommercialOrganizationPipelineParameters"
            )

        # Initialize graphs
        graph_insert = Graph()

        # Get subject URI & graph
        individual_uri = URIRef(parameters.individual_uri)
        graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update properties
        if parameters.legal_uri:
            check_legal = list(
                graph.triples(
                    (
                        individual_uri,
                        URIRef("http://ontology.naas.ai/abi/hasLegalName"),
                        URIRef(parameters.legal_uri),
                    )
                )
            )
            if len(check_legal) == 0:
                graph_insert.add(
                    (individual_uri, ABI.hasLegalName, URIRef(parameters.legal_uri))
                )
        if parameters.ticker_uri:
            check_ticker = list(
                graph.triples(
                    (
                        individual_uri,
                        URIRef("http://ontology.naas.ai/abi/hasTickerSymbol"),
                        URIRef(parameters.ticker_uri),
                    )
                )
            )
            if len(check_ticker) == 0:
                graph_insert.add(
                    (individual_uri, ABI.hasTickerSymbol, URIRef(parameters.ticker_uri))
                )
        if parameters.website_uri:
            check_website = list(
                graph.triples(
                    (
                        individual_uri,
                        URIRef("http://ontology.naas.ai/abi/hasWebsite"),
                        URIRef(parameters.website_uri),
                    )
                )
            )
            if len(check_website) == 0:
                graph_insert.add(
                    (individual_uri, ABI.hasWebsite, URIRef(parameters.website_uri))
                )
        if parameters.linkedin_page_uri:
            check_linkedin_page = list(
                graph.triples(
                    (
                        individual_uri,
                        URIRef("http://ontology.naas.ai/abi/hasLinkedInPage"),
                        URIRef(parameters.linkedin_page_uri),
                    )
                )
            )
            if len(check_linkedin_page) == 0:
                graph_insert.add(
                    (
                        individual_uri,
                        ABI.hasLinkedInPage,
                        URIRef(parameters.linkedin_page_uri),
                    )
                )
        if parameters.logo_url:
            check_logo = list(
                graph.triples(
                    (
                        individual_uri,
                        URIRef("http://ontology.naas.ai/abi/logo"),
                        Literal(parameters.logo_url),
                    )
                )
            )
            if len(check_logo) == 0:
                graph_insert.add(
                    (individual_uri, ABI.logo, Literal(parameters.logo_url))
                )

        # Save graphs to triple store
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_commercial_organization",
                description="Update a commercial organization properties",
                func=lambda **kwargs: self.run(
                    UpdateCommercialOrganizationPipelineParameters(**kwargs)
                ),
                args_schema=UpdateCommercialOrganizationPipelineParameters,
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
