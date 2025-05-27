from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from pydantic import Field
from typing import Optional, Annotated
from rdflib import URIRef, Literal, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
    ABI,
    CCO,
    URI_REGEX,
)
from fastapi import APIRouter
from enum import Enum

@dataclass
class AddCommercialOrganizationPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddCommercialOrganizationPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
        add_individual_pipeline_configuration (AddIndividualPipelineConfiguration): The configuration for the add individual pipeline
    """

    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration


class AddCommercialOrganizationPipelineParameters(PipelineParameters):
    label: Annotated[str, Field(
        description="Name of the commercial organization to be added in class: https://www.commercoreontologies.org/ont00000443",
        example="Naas.ai"
    )]
    legal_uri: Annotated[Optional[str], Field(
        default=None,
        description="Individual URI from class: https://www.commoncoreontologies.org/ont00001331",
        pattern=URI_REGEX
    )]
    ticker_uri: Annotated[Optional[str], Field(
        default=None,
        description="Individual URI from class: http://ontology.naas.ai/abi/Ticker",
        pattern=URI_REGEX
    )]
    website_uri: Annotated[Optional[str], Field(
        default=None,
        description="Individual URI from class: http://ontology.naas.ai/abi/Website",
        pattern=URI_REGEX
    )]
    linkedin_page_uri: Annotated[Optional[str], Field(
        default=None,
        description="Individual URI from class: http://ontology.naas.ai/abi/LinkedInOrganizationPage",
        pattern=URI_REGEX
    )]
    logo_url: Annotated[Optional[str], Field(
        default=None,
        description="Logo URL of the commercial organization.",
        pattern="https?:\/\/.*"
    )]


class AddCommercialOrganizationPipeline(Pipeline):
    """Pipeline for adding a new commercial organization to the ontology."""

    __configuration: AddCommercialOrganizationPipelineConfiguration

    def __init__(self, configuration: AddCommercialOrganizationPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AddCommercialOrganizationPipelineParameters):
            raise ValueError("Parameters must be of type AddCommercialOrganizationPipelineParameters")
        
        # Initialize graphs
        graph_insert = Graph()

        # Create or get subject URI & graph
        individual_uri, graph = self.__add_individual_pipeline.run(
            AddIndividualPipelineParameters(
                class_uri=CCO.ont00000443,
                individual_label=parameters.label
            )
        )
        individual_uri = URIRef(individual_uri)

        # Update properties
        if parameters.legal_uri:
            check_legal = list(graph.triples((individual_uri, URIRef("http://ontology.naas.ai/abi/hasLegalName"), URIRef(parameters.legal_uri))))
            if len(check_legal) == 0:
                graph_insert.add((individual_uri, ABI.hasLegalName, URIRef(parameters.legal_uri)))
        if parameters.ticker_uri:
            check_ticker = list(graph.triples((individual_uri, URIRef("http://ontology.naas.ai/abi/hasTickerSymbol"), URIRef(parameters.ticker_uri))))
            if len(check_ticker) == 0:
                graph_insert.add((individual_uri, ABI.hasTickerSymbol, URIRef(parameters.ticker_uri)))
        if parameters.website_uri:
            check_website = list(graph.triples((individual_uri, URIRef("http://ontology.naas.ai/abi/hasWebsite"), URIRef(parameters.website_uri))))
            if len(check_website) == 0:
                graph_insert.add((individual_uri, ABI.hasWebsite, URIRef(parameters.website_uri)))
        if parameters.linkedin_page_uri:
            check_linkedin_page = list(graph.triples((individual_uri, URIRef("http://ontology.naas.ai/abi/hasLinkedInPage"), URIRef(parameters.linkedin_page_uri))))
            if len(check_linkedin_page) == 0:
                graph_insert.add((individual_uri, ABI.hasLinkedInPage, URIRef(parameters.linkedin_page_uri)))
        if parameters.logo_url:
            check_logo = list(graph.triples((individual_uri, URIRef("http://ontology.naas.ai/abi/logo"), Literal(parameters.logo_url))))
            if len(check_logo) == 0:
                graph_insert.add((individual_uri, ABI.logo, Literal(parameters.logo_url)))

        # Save graphs to triple store
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="add_commercial_organization",
                description="Add a commercial organization with a name and optional website URL to the ontology. Use your internal knowledge to find the website URL.",
                func=lambda **kwargs: self.run(
                    AddCommercialOrganizationPipelineParameters(**kwargs)
                ),
                args_schema=AddCommercialOrganizationPipelineParameters,
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