from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool, BaseTool
from dataclasses import dataclass
from pydantic import Field
from typing import Optional, Annotated
from rdflib import URIRef, Graph
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters,
    URI_REGEX,
    ABI
)
from fastapi import APIRouter
from enum import Enum


@dataclass
class AddTickerPipelineConfiguration(PipelineConfiguration):
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration


class AddTickerPipelineParameters(PipelineParameters):
    label: Annotated[str, Field(
        description="Ticker symbol (e.g., 'AAPL', 'GOOGL') to be added in class: http://ontology.naas.ai/abi/Ticker"
    )]
    individual_uri: Annotated[Optional[str], Field(
        None,
        description="URI of the individual if already known. It must start with 'http://ontology.naas.ai/abi/'.",
        pattern=URI_REGEX
    )]
    organization_uri: Annotated[Optional[str], Field(
        None,
        description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443. It must start with 'http://ontology.naas.ai/abi/'.",
        pattern=URI_REGEX
    )]


class AddTickerPipeline(Pipeline):
    __configuration: AddTickerPipelineConfiguration

    def __init__(self, configuration: AddTickerPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(
            configuration.add_individual_pipeline_configuration
        )

    def run(self, parameters: PipelineParameters) -> Graph:
        if not isinstance(parameters, AddTickerPipelineParameters):
            raise ValueError("Parameters must be of type AddTickerPipelineParameters")
        
        graph = Graph()
        ticker_uri = parameters.individual_uri
        if parameters.label and not ticker_uri:
            ticker_uri, graph = self.__add_individual_pipeline.run(
                AddIndividualPipelineParameters(
                    class_uri=ABI.Ticker, individual_label=parameters.label
                )
            )
        else:
            if ticker_uri.startswith("http://ontology.naas.ai/abi/"):
                ticker_uri = URIRef(ticker_uri)
            else:
                raise ValueError(
                    f"Invalid Ticker URI: {ticker_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        if parameters.organization_uri:
            if parameters.organization_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add(
                    (
                        ticker_uri,
                        ABI.isTickerSymbolOf,
                        URIRef(parameters.organization_uri),
                    )
                )
                graph.add(
                    (
                        URIRef(parameters.organization_uri),
                        ABI.hasTickerSymbol,
                        ticker_uri,
                    )
                )
            else:
                raise ValueError(
                    f"Invalid Organization URI: {parameters.organization_uri}. It must start with 'http://ontology.naas.ai/abi/'."
                )

        self.__configuration.triple_store.insert(graph)
        return graph

    def as_tools(self) -> list[BaseTool]:
        return [
            StructuredTool(
                name="add_ticker",
                description="Add a ticker symbol to the ontology. Requires the ticker symbol.",
                func=lambda **kwargs: self.run(AddTickerPipelineParameters(**kwargs)),
                args_schema=AddTickerPipelineParameters,
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
