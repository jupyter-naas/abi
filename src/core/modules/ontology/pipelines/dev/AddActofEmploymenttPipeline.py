from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from abi.services.triple_store.TripleStorePorts import ITripleStoreService
from langchain_core.tools import StructuredTool
from dataclasses import dataclass
from abi import logger
from fastapi import APIRouter
from pydantic import Field
from typing import List, Optional
from datetime import datetime
from abi.utils.Graph import CCO, ABI, BFO
from rdflib import URIRef, Literal, RDF, OWL, Graph, XSD
from src.core.modules.ontology.pipelines.AddIndividualPipeline import (
    AddIndividualPipeline,
    AddIndividualPipelineConfiguration,
    AddIndividualPipelineParameters
)

@dataclass
class AddActofEmploymentPipelineConfiguration(PipelineConfiguration):
    """Configuration for AddActofEmploymentPipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The triple store service to use
    """
    triple_store: ITripleStoreService
    add_individual_pipeline_configuration: AddIndividualPipelineConfiguration

class AddActofEmploymentPipelineParameters(PipelineParameters):
    participants_uris: List[str] = Field(..., description="List of URIs for the participants in the act of employment.")
    role: str = Field(..., description="Act of employment role or position")
    location: str = Field(..., description="Location of act of employment")
    date_start: datetime = Field(..., description="Start date of act of employment")
    date_end: Optional[datetime] = Field(None, description="End date of act of employment")

class AddEmploymentPipeline(Pipeline):
    """Pipeline for adding a new act of employment to the ontology."""
    __configuration: AddActofEmploymentPipelineConfiguration
    
    def __init__(self, configuration: AddActofEmploymentPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__add_individual_pipeline = AddIndividualPipeline(configuration.add_individual_pipeline_configuration)

    def run(self, parameters: AddEmploymentPipelineParameters) -> Graph:
        # Create employment process URI
        employment_uri, graph = self.__add_individual_pipeline.run(AddIndividualPipelineParameters(
            class_uri=CCO.ont00001226,  # Act of Employment
            individual_label=f"Employment_{parameters.role}_{parameters.date_start.strftime('%Y%m%d')}"
        ))

        # Add participants using BFO relations
        for participant_uri in parameters.participants_uris:
            # BFO_0000057 'has participant'
            graph.add((employment_uri, BFO.BFO_0000057, URIRef(participant_uri)))
            # BFO_0000056 'participates in'
            graph.add((URIRef(participant_uri), BFO.BFO_0000056, employment_uri))

        # Add temporal properties
        graph.add((employment_uri, ABI.start_date, Literal(parameters.date_start.isoformat(), datatype=XSD.dateTime)))
        if parameters.date_end:
            graph.add((employment_uri, ABI.end_date, Literal(parameters.date_end.isoformat(), datatype=XSD.dateTime)))

        # Add role and location
        graph.add((employment_uri, ABI.role, Literal(parameters.role)))
        graph.add((employment_uri, ABI.location, Literal(parameters.location)))
        
        # Save the graph
        self.__configuration.triple_store.insert(graph)
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="ontology_add_employment",
                description="Add an employment process with participants, dates, role, and location to the ontology",
                func=lambda **kwargs: self.run(AddEmploymentPipelineParameters(**kwargs)),
                args_schema=AddEmploymentPipelineParameters
            )   
        ]

    def as_api(self, router: APIRouter) -> None:
        pass 