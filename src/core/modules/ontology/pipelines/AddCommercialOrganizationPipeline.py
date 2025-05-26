from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from langchain.tools import BaseTool
from dataclasses import dataclass
from pydantic import Field
from typing import Optional
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
)

URI_REGEX = r"http:\/\/ontology\.naas\.ai\/abi\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"


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
    label: Optional[str] = Field(
        default=None,
        description="Name of the commercial organization to be added in class: https://www.commoncoreontologies.org/ont00000443",
        example="Naas.ai",
    )
    individual_uri: Optional[str] = Field(
        default=None,
        description="URI of the commercial organization if already known.",
        pattern=URI_REGEX,
    )
    legal_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: https://www.commoncoreontologies.org/ont00001331",
        pattern=URI_REGEX,
    )
    ticker_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: http://ontology.naas.ai/abi/Ticker",
        pattern=URI_REGEX,
    )
    website_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: http://ontology.naas.ai/abi/Website",
        pattern=URI_REGEX,
    )
    linkedin_page_uri: Optional[str] = Field(
        None,
        description="Individual URI from class: http://ontology.naas.ai/abi/LinkedInOrganizationPage",
        pattern=URI_REGEX,
    )
    logo_url: Optional[str] = Field(
        None,
        description="Logo URL of the commercial organization.",
        pattern="https?:\/\/.*",
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

    def run(self, parameters: "AddCommercialOrganizationPipelineParameters") -> Graph:
        # Initialize graphs
        graph_insert = Graph()
        graph_remove = Graph()

        # Create or get subject URI & graph
        if not parameters.individual_uri:
            if parameters.label is None:
                raise ValueError("Label is required when individual_uri is not provided")
            individual_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=CCO.ont00000443,
                    individual_label=parameters.label
                )
            )
        else:
            individual_uri = URIRef(individual_uri)
            graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update existing objects
        legal_uri_exists = False
        ticker_uri_exists = False
        website_uri_exists = False
        linkedin_page_uri_exists = False
        logo_url_exists = False
        for s, p, o in graph:
            if str(p) == "http://www.w3.org/2000/01/rdf-schema#label":
                if parameters.label is not None and str(o) != parameters.label.strip():
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.label.strip())))
            if str(p) == "http://ontology.naas.ai/abi/hasLegalName":
                legal_uri_exists = True
                if parameters.legal_uri is not None and str(o) != parameters.legal_uri:
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, p, s))
                    graph_insert.add((s, p, URIRef(parameters.legal_uri)))
                    graph_insert.add(
                        (URIRef(parameters.legal_uri), ABI.isLegalNameOf, s)
                    )
            if str(p) == "http://ontology.naas.ai/abi/hasTickerSymbol":
                ticker_uri_exists = True
                if (
                    parameters.ticker_uri is not None
                    and str(o) != parameters.ticker_uri
                ):
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, p, s))
                    graph_insert.add((s, p, URIRef(parameters.ticker_uri)))
                    graph_insert.add(
                        (URIRef(parameters.ticker_uri), ABI.isTickerSymbolOf, s)
                    )
            if str(p) == "http://ontology.naas.ai/abi/hasWebsite":
                website_uri_exists = True
                if (
                    parameters.website_uri is not None
                    and str(o) != parameters.website_uri
                ):
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, p, s))
                    graph_insert.add((s, p, URIRef(parameters.website_uri)))
                    graph_insert.add(
                        (URIRef(parameters.website_uri), ABI.isWebsiteOf, s)
                    )
            if str(p) == "http://ontology.naas.ai/abi/hasLinkedInPage":
                linkedin_page_uri_exists = True
                if (
                    parameters.linkedin_page_uri is not None
                    and str(o) != parameters.linkedin_page_uri
                ):
                    graph_remove.add((s, p, o))
                    graph_remove.add((o, p, s))
                    graph_insert.add((s, p, URIRef(parameters.linkedin_page_uri)))
                    graph_insert.add(
                        (URIRef(parameters.linkedin_page_uri), ABI.isLinkedInPageOf, s)
                    )
            if str(p) == "http://ontology.naas.ai/abi/logo":
                logo_url_exists = True
                if (
                    parameters.logo_url is not None
                    and not parameters.logo_url.startswith("https://api.naas.ai/")
                    and not str(o).startswith("https://api.naas.ai/")
                ):
                    graph_remove.add((s, p, o))
                    graph_insert.add((s, p, Literal(parameters.logo_url)))

        # Add new objects
        if parameters.legal_uri and not legal_uri_exists:
            graph_insert.add(
                (individual_uri, ABI.hasLegalName, URIRef(parameters.legal_uri))
            )
            graph_insert.add(
                (URIRef(parameters.legal_uri), ABI.isLegalNameOf, individual_uri)
            )
        if parameters.ticker_uri and not ticker_uri_exists:
            graph_insert.add(
                (individual_uri, ABI.hasTickerSymbol, URIRef(parameters.ticker_uri))
            )
            graph_insert.add(
                (URIRef(parameters.ticker_uri), ABI.isTickerSymbolOf, individual_uri)
            )
        if parameters.website_uri and not website_uri_exists:
            graph_insert.add(
                (individual_uri, ABI.hasWebsite, URIRef(parameters.website_uri))
            )
            graph_insert.add(
                (URIRef(parameters.website_uri), ABI.isWebsiteOf, individual_uri)
            )
        if parameters.linkedin_page_uri and not linkedin_page_uri_exists:
            graph_insert.add(
                (
                    individual_uri,
                    ABI.hasLinkedInPage,
                    URIRef(parameters.linkedin_page_uri),
                )
            )
            graph_insert.add(
                (
                    URIRef(parameters.linkedin_page_uri),
                    ABI.isLinkedInPageOf,
                    individual_uri,
                )
            )
        if parameters.logo_url and not logo_url_exists:
            graph_insert.add((individual_uri, ABI.logo, Literal(parameters.logo_url)))
        # Save graphs to triple store

        self.__configuration.triple_store.insert(graph_insert)
        self.__configuration.triple_store.remove(graph_remove)
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

    def as_api(self) -> None:
        pass