from dataclasses import dataclass
from enum import Enum
from typing import Annotated, Optional

from langchain_core.tools import BaseTool, StructuredTool
from naas_abi_core.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from naas_abi_core.services.triple_store.TripleStorePorts import ITripleStoreService
from naas_abi_core.utils.Expose import APIRouter
from naas_abi_core.utils.Graph import ABI, URI_REGEX
from pydantic import Field
from rdflib import Graph, URIRef


@dataclass
class UpdateTickerPipelineConfiguration(PipelineConfiguration):
    triple_store: ITripleStoreService


class UpdateTickerPipelineParameters(PipelineParameters):
    individual_uri: Annotated[
        str,
        Field(
            description="URI of the ticker. It must start with 'http://ontology.naas.ai/abi/'.",
            pattern=URI_REGEX,
        ),
    ]
    organization_uri: Annotated[
        Optional[str],
        Field(
            None,
            description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443. It must start with 'http://ontology.naas.ai/abi/'.",
            pattern=URI_REGEX,
        ),
    ]


class UpdateTickerPipeline(Pipeline):
    __configuration: UpdateTickerPipelineConfiguration

    def __init__(self, configuration: UpdateTickerPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateTickerPipelineParameters):
            raise ValueError(
                "Parameters must be of type UpdateTickerPipelineParameters"
            )

        # Initialize graphs
        graph_insert = Graph()

        # Get subject URI & graph
        individual_uri = URIRef(parameters.individual_uri)
        graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update properties
        if parameters.organization_uri:
            check_organization_uri = list(
                graph.triples(
                    (
                        individual_uri,
                        ABI.isTickerSymbolOf,
                        URIRef(parameters.organization_uri),
                    )
                )
            )
            if len(check_organization_uri) == 0:
                graph_insert.add(
                    (
                        individual_uri,
                        ABI.isTickerSymbolOf,
                        URIRef(parameters.organization_uri),
                    )
                )

        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_ticker",
                description="Update a ticker symbol in the ontology.",
                func=lambda **kwargs: self.run(
                    UpdateTickerPipelineParameters(**kwargs)
                ),
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
