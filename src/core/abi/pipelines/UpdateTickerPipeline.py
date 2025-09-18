from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from pydantic import Field
from typing import Optional, Annotated
from rdflib import URIRef, Graph
from abi.utils.Graph import URI_REGEX, ABI
from fastapi import APIRouter
from enum import Enum


@dataclass
class UpdateTickerPipelineConfiguration(PipelineConfiguration):
    triple_store: ITripleStoreService


class UpdateTickerPipelineParameters(PipelineParameters):
    individual_uri: Annotated[str, Field(
        description="URI of the ticker. It must start with 'http://ontology.naas.ai/abi/'.",
        pattern=URI_REGEX
    )]
    organization_uri: Annotated[Optional[str], Field(
        None,
        description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443. It must start with 'http://ontology.naas.ai/abi/'.",
        pattern=URI_REGEX
    )]


class UpdateTickerPipeline(Pipeline):
    __configuration: UpdateTickerPipelineConfiguration

    def __init__(self, configuration: UpdateTickerPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateTickerPipelineParameters):
            raise ValueError("Parameters must be of type UpdateTickerPipelineParameters")
        
        # Initialize graphs
        graph_insert = Graph()

        # Get subject URI & graph
        individual_uri = URIRef(parameters.individual_uri)
        graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update properties
        if parameters.organization_uri:
            check_organization_uri = list(graph.triples((individual_uri, ABI.isTickerSymbolOf, URIRef(parameters.organization_uri))))
            if len(check_organization_uri) == 0:
                graph_insert.add((individual_uri, ABI.isTickerSymbolOf, URIRef(parameters.organization_uri)))

        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_ticker",
                description="Update a ticker symbol in the ontology.",
                func=lambda **kwargs: self.run(UpdateTickerPipelineParameters(**kwargs)),
                args_schema=UpdateTickerPipelineParameters,
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