from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from abi.utils.Graph import CCO, ABI
from rdflib import URIRef, Literal, RDF, OWL, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
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
        description="URI of the individual if already known. It must start with 'http://ontology.naas.ai/abi/'.",
    )
    organization_uri: Optional[str] = Field(
        None,
        description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443. It must start with 'http://ontology.naas.ai/abi/'.",
    )


class AddLegalNamePipeline(Pipeline):
    __configuration: AddLegalNamePipelineConfiguration

    def __init__(self, configuration: AddLegalNamePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: AddLegalNamePipelineParameters) -> str:
        graph = Graph()

        legal_name_uri = parameters.individual_uri
        if parameters.label and not legal_name_uri:
            legal_name_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=CCO.ont00001331, individual_label=parameters.label
                )
            )
        else:
            if legal_name_uri.startswith("http://ontology.naas.ai/abi/"):
                legal_name_uri = URIRef(legal_name_uri)
            else:
                raise ValueError(
                    f"Invalid Legal Name URI: {legal_name_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        if parameters.organization_uri:
            if parameters.organization_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (
                        legal_name_uri,
                        ABI.isLegalNameOf,
                        URIRef(parameters.organization_uri),
                    )
                )
                graph.add(
                    (
                        URIRef(parameters.organization_uri),
                        ABI.hasLegalName,
                        legal_name_uri,
                    )
                )
            else:
                raise ValueError(
                    f"Invalid Organization URI: {parameters.organization_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        self.__configuration.triple_store.insert(graph)
        return legal_name_uri

    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_legal_name",
                description="Add a legal name to the ontology. Requires the legal name.",
                func=lambda **kwargs: self.run(
                    AddLegalNamePipelineParameters(**kwargs)
                ),
                args_schema=AddLegalNamePipelineParameters,
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass
