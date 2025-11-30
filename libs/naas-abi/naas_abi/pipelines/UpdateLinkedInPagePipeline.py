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
class UpdateLinkedInPagePipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdateLinkedInPagePipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService


class UpdateLinkedInPagePipelineParameters(PipelineParameters):
    individual_uri: Annotated[
        str, Field(description="URI of the LinkedIn page.", pattern=URI_REGEX)
    ]
    linkedin_id: Annotated[
        Optional[str], Field(None, description="LinkedIn unique ID of the individual.")
    ]
    linkedin_url: Annotated[
        Optional[str],
        Field(None, description="LinkedIn URL with the LinkedIn ID as identifier."),
    ]
    linkedin_public_id: Annotated[
        Optional[str], Field(None, description="LinkedIn Public ID of the individual.")
    ]
    linkedin_public_url: Annotated[
        Optional[str],
        Field(
            None,
            description="LinkedIn Public URL of the individual with the LinkedIn Public ID as identifier.",
            pattern=r"https?://.+\.linkedin\.com/(in|company|school|showcase)/[^?]+",
        ),
    ]
    owner_uri: Annotated[
        Optional[str],
        Field(
            None,
            description="URI of the owner from class: https://www.commoncoreontologies.org/ont00001262 or https://www.commoncoreontologies.org/ont00000443",
            pattern=URI_REGEX,
        ),
    ]


class UpdateLinkedInPagePipeline(Pipeline):
    """Pipeline for updating a LinkedIn page in the ontology."""

    __configuration: UpdateLinkedInPagePipelineConfiguration

    def __init__(self, configuration: UpdateLinkedInPagePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateLinkedInPagePipelineParameters):
            raise ValueError(
                "Parameters must be of type UpdateLinkedInPagePipelineParameters"
            )

        # Initialize graphs
        graph_insert = Graph()

        # Get existing graph
        graph = self.__configuration.triple_store.get_subject_graph(
            parameters.individual_uri
        )
        individual_uri = URIRef(parameters.individual_uri)

        # Update properties
        if parameters.linkedin_id:
            check_id = list(
                graph.triples(
                    (individual_uri, ABI.linkedin_id, Literal(parameters.linkedin_id))
                )
            )
            if len(check_id) == 0:
                graph_insert.add(
                    (individual_uri, ABI.linkedin_id, Literal(parameters.linkedin_id))
                )

        if parameters.linkedin_url:
            check_url = list(
                graph.triples(
                    (individual_uri, ABI.linkedin_url, Literal(parameters.linkedin_url))
                )
            )
            if len(check_url) == 0:
                graph_insert.add(
                    (individual_uri, ABI.linkedin_url, Literal(parameters.linkedin_url))
                )

        if parameters.linkedin_public_id:
            check_public_id = list(
                graph.triples(
                    (
                        individual_uri,
                        ABI.linkedin_public_id,
                        Literal(parameters.linkedin_public_id),
                    )
                )
            )
            if len(check_public_id) == 0:
                graph_insert.add(
                    (
                        individual_uri,
                        ABI.linkedin_public_id,
                        Literal(parameters.linkedin_public_id),
                    )
                )

        if parameters.linkedin_public_url:
            check_public_url = list(
                graph.triples(
                    (
                        individual_uri,
                        ABI.linkedin_public_url,
                        Literal(parameters.linkedin_public_url),
                    )
                )
            )
            if len(check_public_url) == 0:
                graph_insert.add(
                    (
                        individual_uri,
                        ABI.linkedin_public_url,
                        Literal(parameters.linkedin_public_url),
                    )
                )

        if parameters.owner_uri:
            owner_uri = URIRef(parameters.owner_uri)
            check_owner = list(
                graph.triples((individual_uri, ABI.isLinkedInPageOf, owner_uri))
            )
            if len(check_owner) == 0:
                graph_insert.add((individual_uri, ABI.isLinkedInPageOf, owner_uri))
                graph_insert.add((owner_uri, ABI.hasLinkedInPage, individual_uri))

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_linkedin_page",
                description="Update a LinkedIn page in the ontology.",
                func=lambda **kwargs: self.run(
                    UpdateLinkedInPagePipelineParameters(**kwargs)
                ),
                args_schema=UpdateLinkedInPagePipelineParameters,
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
