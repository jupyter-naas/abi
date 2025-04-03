from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi import logger
from pydantic import Field
from abi.utils.Graph import ABI
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from typing import Any
from abi.utils.Graph import ABIGraph as Graph
from rdflib import URIRef

@dataclass
class OrganizationSizePipelineConfiguration(PipelineConfiguration):
    """Configuration for OrganizationSize pipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
    """
    triple_store: ITripleStoreService

class OrganizationSizePipelineParameters(PipelineParameters):
    """Parameters for OrganizationSize pipeline execution.
    
    Attributes:
        organization_uri (str): URI of the organization to analyze
        number_of_employees (int): Number of employees in the organization
    """
    ontology_name: str = Field(..., description="Filename of the ontology store")
    organization_uri: str = Field(..., description="URI of the organization to analyze")
    number_of_employees: int = Field(..., description="Number of employees in the organization")

class OrganizationSizePipeline(Pipeline):
    """Pipeline for categorizing organization size based on employee count."""
    
    __configuration: OrganizationSizePipelineConfiguration
        
    def __init__(self, configuration: OrganizationSizePipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__triple_store = self.__configuration.triple_store

    def trigger(self, event: OntologyEvent, ontology_name:str, triple: tuple[Any, Any, Any]) -> Graph:
        s, p, o = triple
        logger.info(f"==> Triggering organization size pipeline: {s} {p} {o}")
        if str(event) == str(OntologyEvent.INSERT):
            return self.run(OrganizationSizePipelineParameters(
                ontology_name=ontology_name,
                organization_uri=s,
                number_of_employees=o
            ))
        return None

    def run(self, parameters: OrganizationSizePipelineParameters) -> None:
        # Initialize graph
        graph = Graph()
        try:    
            existing_graph = self.__configuration.triple_store.get(parameters.ontology_name)
            # Create new ABIGraph and merge existing data
            for triple in existing_graph:
                graph.add(triple)
        except Exception as e:
            logger.debug(f"Error getting graph: {e}")
        number_of_employees = int(parameters.number_of_employees)
        
        # Determine organization size category
        if number_of_employees < 10:
            organization_size_id = "micro_enterprise"
            organization_size_label = "Micro Enterprise"
            organization_size_description = "Micro Enterprises are businesses with fewer than 10 employees."
        elif number_of_employees < 50:
            organization_size_id = "small_enterprise"
            organization_size_label = "Small Enterprise"
            organization_size_description = "Small Enterprises are businesses with between 10 and 49 employees."
        elif number_of_employees < 250:
            organization_size_id = "medium_enterprise"
            organization_size_label = "SMEs"
            organization_size_description = "Small and Medium Enterprises (SMEs) are businesses with between 50 and 249 employees."
        else:
            organization_size_id = "large_enterprise"
            organization_size_label = "Large Enterprise"
            organization_size_description = "Large Enterprises are businesses with more than 250 employees."

        # Add organization size to graph
        organization_size_uri = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=organization_size_id,
            label=organization_size_label,
            is_a=ABI.OrganizationSize,
            description=organization_size_description,
            ontology_group="General"
        )
        
        # Link organization to its size
        organization_uri = URIRef(parameters.organization_uri)
        graph.add((organization_uri, ABI.hasOrganizationSize, organization_size_uri))
        graph.add((organization_size_uri, ABI.isOrganizationSizeOf, organization_uri))
        
        # Save to ontology store
        logger.info(f"Saving organization size classification to ontology store")
        self.__configuration.triple_store.store(parameters.ontology_name, graph)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [
            StructuredTool(
                name="ontology_add_organization_size",
                description="Add organization size classification to an organization in the ontology store based on the number of employees.",
                func=lambda **kwargs: self.run(OrganizationSizePipelineParameters(**kwargs)),
                args_schema=OrganizationSizePipelineParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass