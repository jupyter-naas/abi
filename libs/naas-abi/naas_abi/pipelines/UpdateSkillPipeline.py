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
class UpdateSkillPipelineConfiguration(PipelineConfiguration):
    """Configuration for UpdateSkillPipeline.

    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """

    triple_store: ITripleStoreService


class UpdateSkillPipelineParameters(PipelineParameters):
    individual_uri: Annotated[
        str, Field(description="URI of the skill.", pattern=URI_REGEX)
    ]
    description: Annotated[
        Optional[str], Field(None, description="Description of the skill")
    ] = None
    person_uri: Annotated[
        Optional[str],
        Field(
            None,
            description="Person URI from class: https://www.commoncoreontologies.org/ont00001262.",
            pattern=URI_REGEX,
        ),
    ] = None


class UpdateSkillPipeline(Pipeline):
    """Pipeline for updating a skill in the ontology."""

    __configuration: UpdateSkillPipelineConfiguration

    def __init__(self, configuration: UpdateSkillPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, UpdateSkillPipelineParameters):
            raise ValueError("Parameters must be of type UpdateSkillPipelineParameters")

        # Initialize a new graph
        graph_insert = Graph()

        # Get subject URI & graph
        individual_uri = URIRef(parameters.individual_uri)
        graph = self.__configuration.triple_store.get_subject_graph(individual_uri)

        # Update properties
        if parameters.description:
            check_description = list(
                graph.triples(
                    (
                        individual_uri,
                        ABI.hasDescription,
                        Literal(parameters.description),
                    )
                )
            )
            if len(check_description) == 0:
                graph_insert.add(
                    (
                        individual_uri,
                        ABI.hasDescription,
                        Literal(parameters.description),
                    )
                )
        if parameters.person_uri:
            check_person_uri = list(
                graph.triples(
                    (individual_uri, ABI.isSkillOf, URIRef(parameters.person_uri))
                )
            )
            if len(check_person_uri) == 0:
                graph_insert.add(
                    (individual_uri, ABI.isSkillOf, URIRef(parameters.person_uri))
                )

        # Save the graph
        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="update_skill",
                description="Update a skill with a description in the ontology.",
                func=lambda **kwargs: self.run(UpdateSkillPipelineParameters(**kwargs)),
                args_schema=UpdateSkillPipelineParameters,
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
