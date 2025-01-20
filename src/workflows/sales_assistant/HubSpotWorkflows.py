from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.integrations.HubSpotIntegration import HubSpotIntegration, HubSpotIntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from langchain_core.tools import StructuredTool
from fastapi import APIRouter

@dataclass
class HubSpotWorkflowsConfiguration(WorkflowConfiguration):
    """Configuration for HubSpotWorkflow.
    
    Attributes:
        hubspot_integration_config (HubSpotIntegrationConfiguration): Configuration for the HubSpot integration
    """
    hubspot_integration_config: HubSpotIntegrationConfiguration

class GetOwnersParameters(WorkflowParameters):
    pass

class SearchContactByEmailParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        email (Optional[str]): Email address to search for
        firstname (Optional[str]): First name to search for
        lastname (Optional[str]): Last name to search for
        properties (Optional[List[str]]): List of contact properties to include in results
    """
    email: Optional[str] = Field(None, description="Optional, Email address to search for")

class SearchContactByNameParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        firstname (Optional[str]): First name to search for
        lastname (Optional[str]): Last name to search for
    """
    firstname: Optional[str] = Field(None, description="Optional, First name to search for")
    lastname: Optional[str] = Field(None, description="Optional, Last name to search for")

class SearchDealByNameParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        name (Optional[str]): Name to search for
    """
    dealname: Optional[str] = Field(None, description="Optional, Name of the deal to search for")

class SearchCompanyByNameParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        name (Optional[str]): Name to search for
    """
    name: Optional[str] = Field(None, description="Optional, Name of the company to search for")

class SearchTaskBySubjectParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        subject (Optional[str]): Subject to search for
    """
    subject: Optional[str] = Field(None, description="Optional, Subject of the task to search for")

class HubSpotWorkflows(Workflow):
    """Search for contacts in HubSpot by email or name."""
    __configuration: HubSpotWorkflowsConfiguration
    
    def __init__(self, configuration: HubSpotWorkflowsConfiguration):
        self.__configuration = configuration
        self.__hubspot_integration = HubSpotIntegration(self.__configuration.hubspot_integration_config)

    def search_contacts_by_email(self, parameters: SearchContactByEmailParameters) -> List[Dict]:
        filters = [
            {
                "propertyName": "email",
                "operator": "EQ",
                "value": parameters.email
            }
        ]
        properties = [
            "firstname", 
            "lastname", 
            "email"
        ]
        sorts = [
            {
                "propertyName": "lastmodifieddate", 
                "direction": "DESCENDING"
            }
        ]
        
        results = self.__hubspot_integration.search_objects("contacts", filters=filters, properties=properties, sorts=sorts)
        return [result.get("properties", {}) for result in results]

    def search_contacts_by_name(self, parameters: SearchContactByNameParameters) -> List[Dict]:
        filters = []
        if parameters.firstname is not None:
            filters.append({
                "propertyName": "firstname",
                "operator": "CONTAINS_TOKEN",
                "value": parameters.firstname
            })
        if parameters.lastname is not None:
            filters.append({
                "propertyName": "lastname",
                "operator": "CONTAINS_TOKEN",
                "value": parameters.lastname
            })
        properties = [
            "firstname", 
            "lastname", 
            "email"
        ]
        sorts = [
            {
                "propertyName": "lastmodifieddate", 
                "direction": "DESCENDING"
            }
        ]
        results = self.__hubspot_integration.search_objects("contacts", filters=filters, properties=properties, sorts=sorts)
        return [result.get("properties", {}) for result in results]
    
    def search_deals_by_name(self, parameters: SearchDealByNameParameters) -> List[Dict]:
        filters = [
            {
                "propertyName": "dealname",
                "operator": "CONTAINS_TOKEN",
                "value": parameters.dealname
            }
        ]
        properties = [
            "dealname", 
            "dealstage", 
            "dealtype", 
            "amount", 
            "closedate"
        ]
        sorts = [
            {
                "propertyName": "hs_lastmodifieddate", 
                "direction": "DESCENDING"
            }
        ]
        results = self.__hubspot_integration.search_objects("deals", filters=filters, properties=properties, sorts=sorts)
        return [result.get("properties", {}) for result in results]
    
    def search_companies_by_name(self, parameters: SearchCompanyByNameParameters) -> List[Dict]:
        filters = [
            {
                "propertyName": "name",
                "operator": "CONTAINS_TOKEN",
                "value": parameters.name
            }
        ]
        properties = [
            "name", 
            "website", 
            "description", 
            "phone", 
            "address"
        ]
        sorts = [
            {
                "propertyName": "hs_lastmodifieddate", 
                "direction": "DESCENDING"
            }
        ]
        results = self.__hubspot_integration.search_objects("companies", filters=filters, properties=properties, sorts=sorts)
        return [result.get("properties", {}) for result in results]
    
    def search_tasks_by_subject(self, parameters: SearchTaskBySubjectParameters) -> List[Dict]:
        filter_groups = [
            {
                "filters": [
                    {
                        "propertyName": "hs_task_status",
                        "operator": "EQ",
                        "value": "NOT_STARTED"
                    },
                    {
                        "propertyName": "hs_task_subject",
                        "operator": "CONTAINS_TOKEN",
                        "value": parameters.subject
                    }
                ]
            },
            {
                "filters": [
                    {
                        "propertyName": "hs_task_status",
                        "operator": "EQ",
                        "value": "NOT_STARTED"
                    },
                    {
                        "propertyName": "hs_task_body",
                        "operator": "CONTAINS_TOKEN",
                        "value": parameters.subject
                    }
                ]
            }
        ]
        properties = [
            "hs_task_subject",
            "hs_task_type",
            "hs_task_body",
            "hs_task_priority",
            "hs_task_status",
            "hs_task_timestamp",
            "hubspot_owner_id"
        ]
        sorts = [
            {
                "propertyName": "hs_lastmodifieddate",
                "direction": "DESCENDING"
            }
        ]
        results = self.__hubspot_integration.search_objects("tasks", filter_groups=filter_groups, properties=properties, sorts=sorts)
        return [result.get("properties", {}) for result in results]
    
    def get_owners(self, parameters: GetOwnersParameters) -> List[Dict]:
        results = self.__hubspot_integration.get_owners()
        return [result.get("properties", {}) for result in results]
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="hubspot_get_owners",
                description="Get the owners of HubSpot contacts",
                func=lambda: self.get_owners(GetOwnersParameters()),
                args_schema=GetOwnersParameters
            ),
            StructuredTool(
                name="hubspot_search_contact_by_email",
                description="Search for HubSpot contacts by email address",
                func=lambda email: self.search_contacts_by_email(SearchContactByEmailParameters(email=email)),
                args_schema=SearchContactByEmailParameters
            ),
            StructuredTool(
                name="hubspot_search_contact_by_name",
                description="Search for HubSpot contacts by first name and/or last name. At least one of firstname or lastname must be provided.",
                func=lambda firstname=None, lastname=None: self.search_contacts_by_name(
                    SearchContactByNameParameters(firstname=firstname, lastname=lastname)
                ),
                args_schema=SearchContactByNameParameters
            ),
            StructuredTool(
                name="hubspot_search_deal_by_name",
                description="Search for deals in HubSpot by name",
                func=lambda dealname: self.search_deals_by_name(SearchDealByNameParameters(dealname=dealname)),
                args_schema=SearchDealByNameParameters
            ),
            StructuredTool(
                name="hubspot_search_company_by_name",
                description="Search for companies in HubSpot by name",
                func=lambda name: self.search_companies_by_name(SearchCompanyByNameParameters(name=name)),
                args_schema=SearchCompanyByNameParameters
            ),
            StructuredTool(
                name="hubspot_search_task_by_subject",
                description="Search for tasks in HubSpot by subject",
                func=lambda subject: self.search_tasks_by_subject(SearchTaskBySubjectParameters(subject=subject)),
                args_schema=SearchTaskBySubjectParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass