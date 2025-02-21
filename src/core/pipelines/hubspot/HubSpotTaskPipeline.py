from abi.pipeline import PipelineConfiguration, Pipeline, PipelineParameters
from dataclasses import dataclass
from src.core.integrations.HubSpotIntegration import HubSpotIntegration, HubSpotIntegrationConfiguration
from abi.utils.Graph import ABIGraph, ABI, BFO
from rdflib import Graph
from datetime import datetime
from abi.services.ontology_store.OntologyStorePorts import IOntologyStoreService
from abi import logger
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from pydantic import Field
from typing import Optional, List
from src import secret, config

LOGO_URL = "https://logo.clearbit.com/hubspot.com"

@dataclass
class HubSpotTaskPipelineConfiguration(PipelineConfiguration):
    """Configuration for HubSpotTaskPipeline.
    
    Attributes:
        hubspot_integration_config (HubSpotIntegrationConfiguration): The HubSpot API integration instance
        ontology_store (IOntologyStoreService): The ontology store service to use
        ontology_store_name (str): Name of the ontology store to use. Defaults to "hubspot"
    """
    hubspot_integration_config: HubSpotIntegrationConfiguration
    ontology_store: IOntologyStoreService
    ontology_store_name: str = "hubspot"


class HubSpotTaskPipelineParameters(PipelineParameters):
    """Parameters for HubSpotTaskPipeline execution.
    
    Attributes:
        task_id (str): HubSpot task ID
        contact_ids (List[str]): List of associated contact IDs
        company_ids (Optional[List[str]]): Optional list of associated company IDs
        deal_ids (Optional[List[str]]): Optional list of associated deal IDs
    """
    task_id: str = Field(..., description="HubSpot task ID")

class HubSpotTaskPipeline(Pipeline):
    """Pipeline for adding a HubSpot task to the ontology."""
    __configuration: HubSpotTaskPipelineConfiguration
    
    def __init__(self, configuration: HubSpotTaskPipelineConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration
        self.__hubspot_integration = HubSpotIntegration(self.__configuration.hubspot_integration_config)

    def run(self, parameters: HubSpotTaskPipelineParameters) -> Graph:
        # Init graph
        try:    
            graph = self.__configuration.ontology_store.get(self.__configuration.ontology_store_name)
        except Exception as e:
            logger.error(f"Error getting graph: {e}")
            graph = ABIGraph()
            
        # # Get task from HubSpot
        # task_data = {
        #     'id': '69354076257',
        #     'properties': {
        #         'hs_createdate': '2025-01-17T16:10:00.619Z',
        #         'hs_lastmodifieddate': '2025-01-20T08:54:22.203Z',
        #         'hs_object_id': '69354076257',
        #         'hs_task_body': 'My task body',
        #         'hs_task_priority': 'NONE',
        #         'hs_task_status': 'NOT_STARTED',
        #         'hs_task_subject': 'SetupABI: Arista ',
        #         'hs_timestamp': '2025-01-22T07:00:00Z',
        #         'hubspot_owner_id': '158372102'
        #     },
        #     'createdAt': '2025-01-17T16:10:00.619Z',
        #     'updatedAt': '2025-01-20T08:54:22.203Z',
        #     'archived': False,
        #     'associations': 
        #         {
        #             'companies': {'results': [{'id': '8117945690','type': 'task_to_company'}]},
        #             'deals': {'results': [{'id': '32126353301', 'type': 'task_to_deal'}]},
        #             'contacts': {'results': [{'id': '1234567890', 'type': 'task_to_contact'}]}
        #         }
        # }

        # Get task data from HubSpotIntegration
        task_data = self.__hubspot_integration.get_task(
            parameters.task_id,
            properties=["hs_task_subject", "hs_task_body", "hs_task_priority", "hs_task_status", "hs_timestamp", "hubspot_owner_id"],
            associations=["contacts", "companies", "deals"]
        )

        # Extract task metadata
        task_id = task_data.get("id")
        task_subject = task_data.get("properties", {}).get("hs_task_subject").strip()
        task_body = task_data.get("properties", {}).get("hs_task_body").strip()
        task_priority = task_data.get("properties", {}).get("hs_task_priority")
        task_status = task_data.get("properties", {}).get("hs_task_status")
        task_timestamp = task_data.get("properties", {}).get("hs_timestamp")
        task_owner_id = task_data.get("properties", {}).get("hubspot_owner_id")
        task_updated_date = task_data.get("updatedAt")

        # Convert timestamp to datetime
        task_due_date = datetime.strptime(task_timestamp, "%Y-%m-%dT%H:%M:%SZ") if task_timestamp else None
        logger.debug(f"Task: {task_subject} - Due: {task_due_date}")

        # Add Process: Task Completion
        task_completion = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(task_id) + "-" + str(int(task_due_date.timestamp())),
            label=task_subject,
            is_a=ABI.TaskCompletion,
            description=task_body,
            priority=task_priority,
            status=task_status,
            due_date=task_due_date,
            updated_date=task_updated_date
        )

        # Add GDC: HubSpotTask
        hubspot_task = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(task_id),
            label=task_subject,
            is_a=ABI.HubSpotTask,
            description=task_body,
            priority=task_priority,
            status=task_status,
            due_date=task_due_date,
            updated_date=task_updated_date
        )
        graph.add((task_completion, BFO.BFO_0000058, hubspot_task))
        graph.add((hubspot_task, BFO.BFO_0000059, task_completion))

        # Add associated contacts
        for contact in task_data.get("associations", {}).get("contacts", {}).get("results", []):
            contact_id = contact.get("id")
            contact_data = self.__hubspot_integration.get_contact(contact_id)
            logger.debug(f"Contact: {contact_data}")
            contact = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=str(contact_id),
                label=contact_data.get("properties", {}).get("email"),
                is_a=ABI.HubSpotContact,
                email=contact_data.get("properties", {}).get("email")
            )
            graph.add((task_completion, ABI.hasAssignee, contact))

        # Add associated companies
        for company in task_data.get("associations", {}).get("companies", {}).get("results", []):
            company_id = company.get("id")
            company_data = self.__hubspot_integration.get_company(company_id)
            logger.debug(f"Company: {company_data}")
            company = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=str(company_id),
                label=company_data.get("properties", {}).get("name"),
                is_a=ABI.HubSpotCompany,
                name=company_data.get("properties", {}).get("name")
            )
            graph.add((task_completion, ABI.hasCompany, company))

        # Add associated deals
        for deal in task_data.get("associations", {}).get("deals", {}).get("results", []):
            deal_id = deal.get("id")
            deal_data = self.__hubspot_integration.get_deal(deal_id)
            logger.debug(f"Deal: {deal_data}")
            deal = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=str(deal_id),
                label=deal_data.get("properties", {}).get("dealname"),
                is_a=ABI.HubSpotDeal,
                name=deal_data.get("properties", {}).get("dealname")
            )
            graph.add((task_completion, ABI.hasDeal, deal))

        # Add temporal information
        if task_due_date:
            temporal_instant = graph.add_individual_to_prefix(
                prefix=ABI,
                uid=str(int(task_due_date.timestamp())),
                label=task_due_date.strftime("%Y-%m-%dT%H:%M:%S%z"),
                is_a=BFO.BFO_0000203
            )
            graph.add((task_completion, BFO.BFO_0000222, temporal_instant))

        # Add owner to agent
        owner_data = next((owner for owner in self.__hubspot_integration.get_owners() if str(owner.get("id")) == str(task_owner_id)), {})
        owner = graph.add_individual_to_prefix(
            prefix=ABI,
            uid=str(task_owner_id),
            label=owner_data.get("firstName") + " " + owner_data.get("lastName"),
            is_a=ABI.HubSpotOwner,
            email=owner_data.get("email")
        )
        graph.add((task_completion, ABI.hasCreator, owner))
        
        self.__configuration.ontology_store.store(self.__configuration.ontology_store_name, graph)
        
        return graph
    
    def as_tools(self) -> list[StructuredTool]:
        return [
            StructuredTool(
                name="hubspot_task_pipeline",
                description="Adds a HubSpot task to the ontology",
                func=lambda **kwargs: self.run(HubSpotTaskPipelineParameters(**kwargs)),
                args_schema=HubSpotTaskPipelineParameters
            )
        ]

    def as_api(
        self, 
        router: APIRouter, 
        route_name: str = "hubspot_task", 
        name: str = "HubSpot Task to Ontology", 
        description: str = "Fetches a specific HubSpot task by ID, extracts its metadata including subject, description, priority, status, and associations with contacts, companies and deals, then maps it to the ontology as a task completion with temporal information and agent relationships.",
        tags: list[str] = []
    ) -> None:
        @router.post(f"/{route_name}", name=name, description=description, tags=tags)
        def run(parameters: HubSpotTaskPipelineParameters):
            return self.run(parameters).serialize(format="turtle")
        
if __name__ == "__main__":
    from abi.services.ontology_store.adaptors.secondary.OntologyStoreService__SecondaryAdaptor__Filesystem import OntologyStoreService__SecondaryAdaptor__Filesystem
    from abi.services.ontology_store.OntologyStoreService import OntologyStoreService

    # Initialize ontology store
    ontology_store = OntologyStoreService(OntologyStoreService__SecondaryAdaptor__Filesystem(store_path=config.ontology_store_path))

    # Initialize HubSpot integration
    hubspot_integration_config = HubSpotIntegrationConfiguration(access_token=secret.get("HUBSPOT_ACCESS_TOKEN"))

    # Initialize pipeline
    pipeline = HubSpotTaskPipeline(HubSpotTaskPipelineConfiguration(
        hubspot_integration_config=hubspot_integration_config,
        ontology_store=ontology_store,
        ontology_store_name="hubspot"
    ))

    # Run pipeline
    pipeline.run(HubSpotTaskPipelineParameters(task_id="69354076257"))