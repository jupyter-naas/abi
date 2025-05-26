from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from pydantic import Field
from typing import Optional
from rdflib import URIRef, Graph
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
class AddLegalNamePipelineConfiguration(PipelineConfiguration):
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration


class AddLegalNamePipelineParameters(PipelineParameters):
    label: str = Field(
        ...,
        description="Legal name to be added in class: https://www.commoncoreontologies.org/ont00001331",
    )
    individual_uri: Optional[str] = Field(
        None,
        description="URI of the individual if already known.",
        pattern=URI_REGEX,
    )
    organization_uri: Optional[str] = Field(
        None,
        description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443.",
        pattern=URI_REGEX,
    )


class AddLegalNamePipeline(Pipeline):
    __configuration: AddLegalNamePipelineConfiguration

    def __init__(self, configuration: AddLegalNamePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddLegalNamePipelineParameters) -> Graph:
        # Init graph
        graph_insert = Graph()
        organization_uri = None
        if parameters.organization_uri:
            organization_uri = URIRef(parameters.organization_uri)

        # Add legal name    
        if parameters.label and not parameters.individual_uri:
            legal_name_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=CCO.ont00001331, 
                    individual_label=parameters.label
                )
            )
            legal_name_uri = URIRef(legal_name_uri)
        else:
            graph = self.__configuration.triple_store.get_subject_graph(parameters.individual_uri)
            legal_name_uri = URIRef(parameters.individual_uri)

        # Update properties
        organization_uri_exists = False
        for s, p, o in graph:
            if str(p) == str(ABI.isLegalNameOf) and str(o) == str(organization_uri):
                organization_uri_exists = True

        if not organization_uri_exists:
            graph_insert.add((legal_name_uri, ABI.isLegalNameOf, organization_uri))

        self.__configuration.triple_store.insert(graph_insert)
        graph += graph_insert
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="add_legal_name",
                description="Add a legal name to the ontology. Requires the legal name.",
                func=lambda **kwargs: self.run(
                    AddLegalNamePipelineParameters(**kwargs)
                ),
                args_schema=AddLegalNamePipelineParameters,
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
