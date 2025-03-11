from abi.workflow import Workflow, WorkflowConfiguration
from abi.workflow.workflow import WorkflowParameters
from src.core.modules.common.integrations.HubSpotIntegration import HubSpotIntegration, HubSpotIntegrationConfiguration
from dataclasses import dataclass
from pydantic import BaseModel, Field
from typing import Dict, Optional, List
from langchain_core.tools import StructuredTool
from fastapi import APIRouter
from datetime import datetime, timedelta

LOGO_URL = "https://logo.clearbit.com/hubspot.com"

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
    """
    email: Optional[str] = Field(None, description="Optional, Email address to search for or domain to search for")

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

class SearchTaskByOwnerParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        owner_id (Optional[str]): ID of the owner to search for
    """
    owner_id: Optional[str] = Field(None, description="Optional, ID of the owner to search for")

class CreateTaskParameters(WorkflowParameters):
    """Parameters for HubSpotWorkflows.
    
    Attributes:
        subject (str): Subject of the task to create
    """
    subject: str = Field(..., description="Subject of the task to create")
    body: str = Field(None, description="Task notes/description")
    type: Optional[str] = Field("TODO", description="Type of task (EMAIL, CALL, or TODO). Use default TODO if not specified")
    priority: Optional[str] = Field("MEDIUM", description="Priority level (LOW, MEDIUM, or HIGH)")
    due_date: Optional[str] = Field(None, description="Due date for task in format YYYY-MM-DD")
    owner_id: Optional[str] = Field(None, description="ID of assigned user")
    contact_ids: Optional[List[str]] = Field([], description="Optional list of contact IDs to associate with the task.")
    company_ids: Optional[List[str]] = Field([], description="Optional list of company IDs to associate with the task.")
    deal_ids: Optional[List[str]] = Field([], description="Optional list of deal IDs to associate with the task.")

class UpdateTaskParameters(WorkflowParameters):
    task_id: str = Field(..., description="ID of the task to update")
    subject: Optional[str] = Field(None, description="Task title")
    body: Optional[str] = Field(None, description="Task notes/description")
    type: Optional[str] = Field("TODO", description="Type of task (EMAIL, CALL, or TODO). Use default TODO if not specified")
    status: Optional[str] = Field("NOT_STARTED", description="Status NOT_STARTED or COMPLETED")
    priority: Optional[str] = Field("MEDIUM", description="Priority level (LOW, MEDIUM, or HIGH)")
    due_date: Optional[str] = Field(None, description="Due date for task in format YYYY-MM-DD")
    owner_id: Optional[str] = Field(None, description="ID of assigned user")
    contact_ids: Optional[List[str]] = Field([], description="Optional list of contact IDs to associate with the task.")
    company_ids: Optional[List[str]] = Field([], description="Optional list of company IDs to associate with the task.")
    deal_ids: Optional[List[str]] = Field([], description="Optional list of deal IDs to associate with the task.")

class DeleteTaskParameters(WorkflowParameters):
    task_id: str = Field(..., description="ID of the task to delete")

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
                "operator": "CONTAINS_TOKEN",
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
                "propertyName": "createdate", 
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
                "propertyName": "createdate", 
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
    
    def search_tasks_by_owner(self, parameters: SearchTaskByOwnerParameters) -> List[Dict]:
        filters = [
            {
                "propertyName": "hubspot_owner_id",
                "operator": "EQ",
                "value": parameters.owner_id
            },
            {
                "propertyName": "hs_task_status",
                "operator": "EQ",
                "value": "NOT_STARTED"
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
        results = self.__hubspot_integration.search_objects("tasks", filters=filters, properties=properties, sorts=sorts)
        return [result.get("properties", {}) for result in results]
    
    def get_owners(self, parameters: GetOwnersParameters) -> List[Dict]:
        results = self.__hubspot_integration.get_owners()
        return results
    
    def create_task(self, parameters: CreateTaskParameters) -> Dict:
        if parameters.due_date is not None:
            due_date = int((datetime.strptime(parameters.due_date, "%Y-%m-%d")).replace(hour=12, minute=0, second=0, microsecond=0).timestamp() * 1000)
        else:
            due_date = None

        result = self.__hubspot_integration.create_task(
            subject=parameters.subject,
            type=parameters.type,
            body=parameters.body,
            status="NOT_STARTED",
            priority=parameters.priority,
            due_date=due_date,
            owner_id=parameters.owner_id,
            contact_ids=parameters.contact_ids,
            company_ids=parameters.company_ids,
            deal_ids=parameters.deal_ids
        )
        return result
    
    def update_task(self, parameters: UpdateTaskParameters) -> Dict:
        if parameters.due_date is not None:
            due_date = int((datetime.strptime(parameters.due_date, "%Y-%m-%d")).replace(hour=12, minute=0, second=0, microsecond=0).timestamp() * 1000)
        else:
            due_date = None

        result = self.__hubspot_integration.update_task(
            task_id=parameters.task_id,
            subject=parameters.subject,
            body=parameters.body,
            type=parameters.type,
            priority=parameters.priority,
            status=parameters.status,
            due_date=due_date,
            owner_id=parameters.owner_id,
            contact_ids=parameters.contact_ids,
            company_ids=parameters.company_ids,
            deal_ids=parameters.deal_ids
        )
        return result
    
    def delete_task(self, parameters: DeleteTaskParameters) -> Dict:
        result = self.__hubspot_integration.delete_task(
            task_id=parameters.task_id
        )
        return result
    
    def as_tools(self) -> list[StructuredTool]:
        """Returns a list of LangChain tools for this workflow.
        
        Returns:
            list[StructuredTool]: List containing the workflow tool
        """
        return [
            StructuredTool(
                name="hubspot_get_owners",
                description="Get the owners/users of HubSpot.",
                func=lambda: self.get_owners(GetOwnersParameters()),
                args_schema=GetOwnersParameters
            ),
            StructuredTool(
                name="hubspot_search_contact_by_email",
                description="Search for HubSpot contacts by email address.",
                func=lambda email: self.search_contacts_by_email(SearchContactByEmailParameters(email=email)),
                args_schema=SearchContactByEmailParameters
            ),
            StructuredTool(
                name="hubspot_search_contact_by_name",
                description="Search for HubSpot contacts by first name and/or last name. At least one of firstname or lastname must be provided.",
                func=lambda **kwargs: self.search_contacts_by_name(SearchContactByNameParameters(**kwargs)),
                args_schema=SearchContactByNameParameters
            ),
            StructuredTool(
                name="hubspot_search_deal_by_name",
                description="Search for deals in HubSpot by name.",
                func=lambda dealname: self.search_deals_by_name(SearchDealByNameParameters(dealname=dealname)),
                args_schema=SearchDealByNameParameters
            ),
            StructuredTool(
                name="hubspot_search_company_by_name",
                description="Search for companies in HubSpot by name.",
                func=lambda name: self.search_companies_by_name(SearchCompanyByNameParameters(name=name)),
                args_schema=SearchCompanyByNameParameters
            ),
            StructuredTool(
                name="hubspot_search_task_by_subject",
                description="Search for tasks in HubSpot by subject.",
                func=lambda subject: self.search_tasks_by_subject(SearchTaskBySubjectParameters(subject=subject)),
                args_schema=SearchTaskBySubjectParameters
            ),
            StructuredTool(
                name="hubspot_search_task_by_owner",
                description="Search for tasks in HubSpot by owner ID.",
                func=lambda owner_id: self.search_tasks_by_owner(SearchTaskByOwnerParameters(owner_id=owner_id)),
                args_schema=SearchTaskByOwnerParameters
            ),
            StructuredTool(
                name="hubspot_create_task",
                description="Create a new task in HubSpot.",
                func=lambda **kwargs: self.create_task(CreateTaskParameters(**kwargs)),
                args_schema=CreateTaskParameters
            ),
            StructuredTool(
                name="hubspot_update_task",
                description="Update a task in HubSpot.",
                func=lambda **kwargs: self.update_task(**kwargs),
                args_schema=UpdateTaskParameters
            ),
            StructuredTool(
                name="hubspot_delete_task",
                description="Delete a task in HubSpot.",
                func=lambda task_id: self.delete_task(DeleteTaskParameters(task_id=task_id)),
                args_schema=DeleteTaskParameters
            )
        ]

    def as_api(self, router: APIRouter) -> None:
        pass