from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from langchain.tools import BaseTool
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

        # Add legal name    
        if parameters.label and not parameters.individual_uri:
            legal_name_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=CCO.ont00001331, 
                    individual_label=parameters.label
                )
            )
        legal_name_uri = URIRef(parameters.individual_uri)

        # Update properties
        organization_uri_exists = False
        for s, p, o in graph:
            if str(p) == str(ABI.isLegalNameOf) and str(o) == str(parameters.organization_uri):
                organization_uri_exists = True

        if not organization_uri_exists:
            graph_insert.add((legal_name_uri, ABI.isLegalNameOf, URIRef(parameters.organization_uri)))

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

    def as_api(self) -> None:
        pass
