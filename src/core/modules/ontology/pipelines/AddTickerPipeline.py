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
    AddIndividualPipelineParameters
)

@dataclass
class AddTickerPipelineConfiguration(PipelineConfiguration):
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddTickerPipelineParameters(PipelineParameters):
    label: str = Field(..., description="Ticker symbol (e.g., 'AAPL', 'GOOGL') to be added in class: http://ontology.naas.ai/abi/Ticker")
    individual_uri: Optional[str] = Field(None, description="URI of the individual if already known. It must start with 'http://ontology.naas.ai/abi/'.")
    organization_uri: Optional[str] = Field(None, description="Organization URI from class: https://www.commoncoreontologies.org/ont00000443. It must start with 'http://ontology.naas.ai/abi/'.")

class AddTickerPipeline(Pipeline):
    __configuration: AddTickerPipelineConfiguration
    
    def __init__(self, configuration: AddTickerPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddTickerPipelineParameters) -> str:
        graph = Graph()

        ticker_uri = parameters.individual_uri
        if parameters.label and not ticker_uri:
            ticker_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
                class_uri=ABI.Ticker,
                individual_label=parameters.label
            ))
        else:
            if ticker_uri.startswith("http://ontology.naas.ai/abi/"):
                ticker_uri = URIRef(ticker_uri)
            else:
                raise ValueError(f"Invalid Ticker URI: {ticker_uri}. It must start with 'http://ontology.naas.ai/abi/'.")

        if parameters.organization_uri:
            if parameters.organization_uri.startswith("http://ontology.naas.ai/abi/"):
                graph.add((ticker_uri, ABI.isTickerSymbolOf, URIRef(parameters.organization_uri)))
                graph.add((URIRef(parameters.organization_uri), ABI.hasTickerSymbol, ticker_uri))
            else:
                raise ValueError(f"Invalid Organization URI: {parameters.organization_uri}. It must start with 'http://ontology.naas.ai/abi/'.")

        self.__configuration.triple_store.insert(graph)
        return ticker_uri
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_ticker",
                description="Add a ticker symbol to the ontology. Requires the ticker symbol.",
                func=lambda **kwargs: self.run(AddTickerPipelineParameters(**kwargs)),
                args_schema=AddTickerPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 