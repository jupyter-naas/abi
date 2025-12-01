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
class UpdateLegalNamePipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdateLegalNamePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService


class UpdateLegalNamePipelineParameters(PipelineParameters):
    individual_uri: Annotated[
        str, Field(description="URI of the legal name.", pattern=URI_REGEX)
    ]
    organization_uri: Annotated[
        Optional[str],
        Field(
            None,
            description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443.",
            pattern=URI_REGEX,
        ),
    ]


class UpdateLegalNamePipeline(Pipeline):
    __configuration: UpdateLegalNamePipelineConfiguration

    def __init__(self, configuration: UpdateLegalNamePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateLegalNamePipelineParameters):
            raise ValueError(
                "Parameters must be of type UpdateLegalNamePipelineParameters"
            )

        # Init graph
        graph_insert = Graph()

        # Get subject URI & graph
        individual_uri = URIRef(parameters.individual_uri)
        graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update properties
        if parameters.organization_uri:
            check_organization = list(
                graph.triples(
                    (
                        individual_uri,
                        ABI.isLegalNameOf,
                        URIRef(parameters.organization_uri),
                    )
                )
            )
            if len(check_organization) == 0:
                graph_insert.add(
                    (
                        individual_uri,
                        ABI.isLegalNameOf,
                        URIRef(parameters.organization_uri),
                    )
                )

        # Save graph to triple store
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_legal_name",
                description="Update a legal name in the ontology.",
                func=lambda **kwargs: self.run(
                    UpdateLegalNamePipelineParameters(**kwargs)
                ),
                args_schema=UpdateLegalNamePipelineParameters,
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
