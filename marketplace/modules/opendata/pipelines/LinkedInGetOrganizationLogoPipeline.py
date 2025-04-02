from abi.pipeline import Pipeline, PipelineConfiguration, PipelineParameters
from dataclasses import dataclass
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from abi import logger
from pydantic import Field
from abi.utils.Graph import ABI
from abi.services.triple_store.TripleStorePorts import ITripleStoreService, OntologyEvent
from src import services
from typing import Optional, Any
from abi.utils.Graph import ABIGraph as Graph
from rdflib import URIRef, Literal

from ..workflows.LinkedInOrganizationsWorkflows import LinkedInOrganizationWorkflows, LinkedInOrganizationWorkflowsConfiguration, LinkedInOrganizationParameters


@dataclass
class LinkedInGetOrganizationLogoPipelineConfiguration(PipelineConfiguration):
    """Configuration for LinkedInGetOrganizationLogo pipeline.
    
    Attributes:
        triple_store (ITripleStoreService): The ontology store service to use
        linkedin_organization_workflows_config (LinkedInOrganizationWorkflowsConfiguration): Configuration for LinkedIn organization workflows
    """
    triple_store: ITripleStoreService
    linkedin_organization_workflows_config: LinkedInOrganizationWorkflowsConfiguration

class LinkedInGetOrganizationLogoPipelineParameters(PipelineParameters):
    """Parameters for LinkedInGetOrganizationLogo pipeline execution.
    
    Attributes:
        filename (str): Filename of the ontology store
        subject (str): URI of the subject in the ontology store
        predicate (str): Predicate of the subject in the ontology store
        object (str): URI of the object in the ontology store
        use_cache (bool): Whether to use cached data. Defaults to True
    """
    ontology_name: str = Field(..., description="Filename of the ontology store")
    organization_uri: str = Field(..., description="URI of the organization")

class LinkedInGetOrganizationLogoPipeline(Pipeline):
    """Pipeline for updating organization logos in the ontology store."""
    
    __configuration: LinkedInGetOrganizationLogoPipelineConfiguration
        
    def __init__(self, configuration: LinkedInGetOrganizationLogoPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__triple_store = self.__configuration.triple_store
        self.__linkedin_organization_workflows = LinkedInOrganizationWorkflows(configuration.linkedin_organization_workflows_config)
        
    def trigger(self, event: OntologyEvent, ontology_name:str, triple: tuple[Any, Any, Any]) -> Graph:
        s, p, o = triple
        logger.info(f"==> Triggering LinkedIn Get Organization Logo Pipeline: {s} {p} {o}")
        if str(event) == str(OntologyEvent.INSERT):
            return self.run(LinkedInGetOrganizationLogoPipelineParameters(
                ontology_name=ontology_name,
                organization_uri=s
            ))
        return None
        
    def run(self, parameters: LinkedInGetOrganizationLogoPipelineParameters) -> None:
        # Initialize graph
        graph = self.__triple_store.get(parameters.ontology_name)

        # Query ontology to get organization name
        logger.info(f"-----> Get organization name from ontology: {parameters.ontology_name}")
        query = f"""
            PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
            SELECT ?label
            WHERE {{
                <{parameters.organization_uri}> rdfs:label ?label .
            }}
        """
        results = self.__triple_store.query(query)
        for row in results:
            organization_name = row.get('label')
            logger.info(f"Organization name: {organization_name}")
            organization_logo_url = self.__linkedin_organization_workflows.get_organization_logo_url(LinkedInOrganizationParameters(organization_name=organization_name))
            logger.info(f"-----> Adding organization logo: {organization_logo_url}")
            graph.add((URIRef(parameters.organization_uri), ABI["logo"], Literal(organization_logo_url)))

        # Save graph
        logger.info(f"-----> Saving graph to ontology store")
        self.__configuration.triple_store.store(parameters.ontology_name, graph)

    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this pipeline."""
        return [
            StructuredTool(
                name="ontology_update_organization_logo_from_linkedin",
                description="Updates organization logos in the ontology store using LinkedIn data",
                func=lambda **kwargs: self.run(LinkedInGetOrganizationLogoPipelineParameters(**kwargs)),
                args_schema=LinkedInGetOrganizationLogoPipelineParameters
            )
        ]
    
    def as_api(self, router: APIRouter) -> None:
        pass