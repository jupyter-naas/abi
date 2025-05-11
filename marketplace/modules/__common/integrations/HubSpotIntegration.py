from typing import Dict, List, Optional
from dataclasses import dataclass
from lib.abi.integration.integration import (
    Integration,
    IntegrationConnectionError,
    IntegrationConfiguration,
)
import requests
from datetime import datetime, timezone
import pandas as pd
import pytz

LOGO_URL = "https://logo.clearbit.com/hubspot.com"


@dataclass
class HubSpotIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for HubSpot integration.

    Attributes:
        access_token (str): HubSpot API access token
        base_url (str): Base URL for HubSpot API
    """

    access_token: str
    base_url: str = "https://api.hubapi.com"


class HubSpotIntegration(Integration):
    """HubSpot API integration client.

    This integration provides methods to interact with HubSpot's API endpoints.
    """

    __configuration: HubSpotIntegrationConfiguration

    def __init__(self, configuration: HubSpotIntegrationConfiguration):
        """Initialize HubSpot client with access token."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def _make_request(
        self, method: str, endpoint: str, data: Dict = None, params: Dict = None
    ) -> Dict:
        """Make HTTP request to HubSpot API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, json=data, params=params
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"HubSpot API request failed: {str(e)}")

    def __get_all(
        self,
        endpoint: str,
        hs_properties: Optional[List[str]] = None,
        limit: Optional[int] = -1,
    ) -> List[Dict]:
        """Get all objects from a specified endpoint with optional property filtering."""
        items = []
        params = {}
        if hs_properties is not None:
            params["properties"] = ",".join(hs_properties)
        more_page = True
        while more_page:
            data = self._make_request("GET", endpoint, params=params)
            for row in data.get("results", []):
                properties = row.get("properties", {})
                items.append(properties)
            if "paging" in data:
                params["after"] = data["paging"]["next"]["after"]
            else:
                more_page = False
            if limit > 0 and len(items) >= limit:
                more_page = False
        params.pop("after", None)
        if hs_properties:
            params.pop("properties", None)
        return items

    def search_objects(
        self,
        object_type: str,
        filters: List[Dict] = [],
        filter_groups: List[Dict] = [],
        properties: Optional[List[str]] = None,
        sorts: List[Dict] = [],
        limit: int = 10,
    ) -> List[Dict]:
        """Search for objects in HubSpot using the Search API.

        Args:
            object_type: Type of object to search for (contacts, companies, deals)
            filters: List of filter conditions.
            filter_groups: List of filter groups.
            properties: Optional list of properties to include in results
            sorts: List of dictionaries that specify the property to sort by and direction
            limit: Maximum number of results to return (default: 100)

        Returns:
            List of dictionaries containing search results with specified properties
        """
        data = {
            "properties": properties if properties else [],
            "sorts": sorts,
            "limit": limit,
        }
        if filters:
            data["filterGroups"] = [{"filters": filters}]
        elif filter_groups:
            data["filterGroups"] = filter_groups
        return self._make_request(
            "POST", f"/crm/v3/objects/{object_type}/search", data=data
        ).get("results", [])

    def list_properties(self, object_type: str) -> List[Dict]:
        """List properties of a specified HubSpot object type."""
        url = f"{self.__configuration.base_url}/crm/v3/properties/{object_type}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            properties_data = response.json()
            properties = properties_data["results"]
            return properties
        else:
            return []

    def get_associations(
        self,
        from_object_type: str,
        object_ids: List[str],
        to_object_type: str,
        after: Optional[str] = None,
        limit: Optional[int] = 100,
    ) -> Dict:
        """Get associations between objects in HubSpot.

        Args:
            from_object_type: Type of the source objects (contacts, companies, deals, etc.)
            object_ids: List of source object IDs to get associations for
            to_object_type: Type of the target objects to get associations for
            after: Optional cursor for pagination
            limit: Maximum number of results to return (default: 500)
        """
        results = []
        for object_id in object_ids:
            endpoint = f"/crm/v4/objects/{from_object_type}/{object_id}/associations/{to_object_type}"
            params = {"limit": limit}
            if after:
                params["after"] = after
            result = self._make_request("GET", endpoint, params=params)
            results.append(result)

        return {"results": results}

    def list_contacts(
        self, properties: Optional[List[str]] = None, limit: Optional[int] = 10
    ) -> pd.DataFrame:
        """Get all contacts from HubSpot with optional property filtering.

        Args:
            properties: Optional list of contact properties to include. If None, includes all properties.

        Returns:
            DataFrame containing all contacts with specified properties.
        """
        return self.__get_all(
            "/crm/v3/objects/contacts", hs_properties=properties, limit=limit
        )

    def get_contact(
        self,
        contact_id: str,
        properties: Optional[List[str]] = None,
        associations: Optional[List[str]] = None,
    ) -> Dict:
        """Get a contact by ID.

        Args:
            contact_id: Contact ID
            properties: Optional list of contact properties to include
            associations: Optional list of associations to include

        Returns:
            Dict containing the contact data
        """
        params = {}
        if properties:
            params["properties"] = ",".join(properties)
        if associations:
            params["associations"] = ",".join(associations)

        return self._make_request(
            "GET", f"/crm/v3/objects/contacts/{contact_id}", params=params
        )

    def get_contact_by_email(
        self,
        email: str,
        properties: Optional[List[str]] = None,
        associations: Optional[List[str]] = None,
    ) -> Dict:
        """Get a contact by email address.

        Args:
            email: Email address of the contact
            properties: Optional list of contact properties to include
            associations: Optional list of associations to include

        Returns:
            Dict containing the contact data
        """
        params = {"idProperty": "email"}
        if properties:
            params["properties"] = ",".join(properties)
        if associations:
            params["associations"] = ",".join(associations)

        return self._make_request(
            "GET", f"/crm/v3/objects/contacts/{email}", params=params
        )

    def create_contact(self, properties: Dict) -> Dict:
        """Create a new contact in HubSpot."""
        data = {"properties": properties}
        return self._make_request("POST", "/crm/v3/objects/contacts", data)

    def update_contact(self, contact_id: str, properties: Dict) -> Dict:
        """Update an existing contact in HubSpot."""
        data = {"properties": properties}
        return self._make_request(
            "PATCH", f"/crm/v3/objects/contacts/{contact_id}", data
        )

    def delete_contact(self, contact_id: str) -> Dict:
        """Delete an existing contact in HubSpot."""
        return self._make_request("DELETE", f"/crm/v3/objects/contacts/{contact_id}")

    def get_owners(self) -> List[Dict]:
        return self._make_request("GET", "/crm/v3/owners")["results"]

    def list_pipeline_stages(
        self, pipeline: Optional[str] = None, pipeline_id: Optional[str] = None
    ) -> List[Dict]:
        """Get all pipeline stages or stages for a specific pipeline.

        Args:
            pipeline: Optional pipeline name to filter by
            pipeline_id: Optional pipeline ID to filter by

        Returns:
            List of dictionaries containing pipeline stages with fields:
            - pipeline: Pipeline name
            - pipeline_id: Pipeline ID
            - dealstage_label: Stage label
            - dealstage_id: Stage ID
            - displayOrder: Display order of stage
            - dealclosed: Whether stage represents closed deal
            - probability: Success probability for stage
            - createdAt: Stage creation timestamp
            - updatedAt: Stage last update timestamp
            - archived: Whether stage is archived
        """
        response = self._make_request("GET", "/crm/v3/pipelines/deals")

        deal_stages = []
        results = response.get("results", [])

        for res in results:
            stages = res.get("stages", [])
            for stage in stages:
                deal_stage = {
                    "pipeline": res.get("label"),
                    "pipeline_id": res.get("id"),
                    "dealstage_label": stage.get("label"),
                    "dealstage_id": stage.get("id"),
                    "displayOrder": stage.get("displayOrder"),
                    "dealclosed": stage.get("metadata", {}).get("isClosed"),
                    "probability": stage.get("metadata", {}).get("probability"),
                    "createdAt": stage.get("createdAt"),
                    "updatedAt": stage.get("updatedAt"),
                    "archived": stage.get("archived"),
                }

                # Filter if pipeline name or ID provided
                if pipeline is not None and str(deal_stage["pipeline"]) != str(
                    pipeline
                ):
                    continue
                if pipeline_id is not None and str(deal_stage["pipeline_id"]) != str(
                    pipeline_id
                ):
                    continue

                deal_stages.append(deal_stage)

        # Sort by pipeline and display order
        deal_stages.sort(key=lambda x: (x["pipeline"], x["displayOrder"]))
        return deal_stages

    def list_deals(
        self, properties: Optional[List[str]] = None, limit: Optional[int] = 10
    ) -> pd.DataFrame:
        """Get all deals from HubSpot with optional property filtering.

        Args:
            properties: Optional list of deal properties to include. If None, includes all properties.
            limit: Maximum number of results to return. Defaults to 10.

        Returns:
            DataFrame containing all deals with specified properties.
        """
        return self.__get_all(
            "/crm/v3/objects/deals", hs_properties=properties, limit=limit
        )

    def get_deal(self, deal_id: str, properties: Optional[List[str]] = None) -> Dict:
        """Get a deal by ID.

        Args:
            deal_id: Deal ID
            properties: Optional list of deal properties to include

        Returns:
            Dict containing the deal data
        """
        params = {}
        if properties:
            params["properties"] = ",".join(properties)
        return self._make_request(
            "GET", f"/crm/v3/objects/deals/{deal_id}", params=params
        )

    def create_deal(self, properties: Dict) -> Dict:
        """Create a new deal in HubSpot."""
        data = {"properties": properties}
        return self._make_request("POST", "/crm/v3/objects/deals", data)

    def update_deal(self, deal_id: str, properties: Dict) -> Dict:
        """Update an existing deal in HubSpot."""
        data = {"properties": properties}
        return self._make_request("PATCH", f"/crm/v3/objects/deals/{deal_id}", data)

    def delete_deal(self, deal_id: str) -> Dict:
        """Delete an existing deal in HubSpot."""
        return self._make_request("DELETE", f"/crm/v3/objects/deals/{deal_id}")

    def list_companies(self, properties: Optional[List[str]] = None) -> pd.DataFrame:
        """Get all companies from HubSpot with optional property filtering.

        Args:
            properties: Optional list of company properties to include. If None, includes all properties.

        Returns:
            DataFrame containing all companies with specified properties.
        """
        return self.__get_all("/crm/v3/objects/companies", properties)

    def get_company(
        self, company_id: str, properties: Optional[List[str]] = None
    ) -> Dict:
        """Get a company by ID.

        Args:
            company_id: Company ID
            properties: Optional list of company properties to include

        Returns:
            Dict containing the company data
        """
        params = {}
        if properties:
            params["properties"] = ",".join(properties)
        return self._make_request(
            "GET", f"/crm/v3/objects/companies/{company_id}", params=params
        )

    def create_company(self, properties: Dict) -> Dict:
        """Create a new company in HubSpot."""
        data = {"properties": properties}
        return self._make_request("POST", "/crm/v3/objects/companies", data)

    def update_company(self, company_id: str, properties: Dict) -> Dict:
        """Update an existing company in HubSpot."""
        data = {"properties": properties}
        return self._make_request(
            "PATCH", f"/crm/v3/objects/companies/{company_id}", data
        )

    def delete_company(self, company_id: str) -> Dict:
        """Delete an existing company in HubSpot."""
        return self._make_request("DELETE", f"/crm/v3/objects/companies/{company_id}")

    def list_tasks(
        self,
        properties: Optional[List[str]] = None,
        limit: Optional[int] = 10,
    ) -> List[Dict]:
        """Get all tasks from HubSpot with optional filtering and pagination.

        Args:
            properties: Optional list of task properties to include. If None, includes all properties.
            limit: Maximum number of results to return per page. Defaults to 10.

        Returns:
            DataFrame containing tasks with specified properties.
        """
        return self.__get_all(
            "/crm/v3/objects/tasks", hs_properties=properties, limit=limit
        )

    def get_task(
        self,
        task_id: str,
        properties: Optional[List[str]] = None,
        associations: Optional[List[str]] = None,
    ) -> Dict:
        """Get a task by ID or unique property value.

        Args:
            task_id: Task ID or unique property value
            properties: Optional list of task properties to include in the response.
                If any specified properties don't exist, they will be ignored.
            properties_with_history: Optional list of properties to return with their history
                of previous values. If any specified properties don't exist, they will be ignored.
            associations: Optional list of object types to retrieve associated IDs for.
                If any specified associations don't exist, they will be ignored.
            archived: Whether to return only archived tasks. Defaults to False.
            id_property: Optional name of a unique property to use for looking up the task
                instead of using the internal task ID.

        Returns:
            Dict containing the task data
        """
        params = {}
        if properties:
            params["properties"] = ",".join(properties)
        if associations:
            params["associations"] = ",".join(associations)

        return self._make_request(
            "GET", f"/crm/v3/objects/tasks/{task_id}", params=params
        )

    def _create_task_properties(
        self,
        subject: Optional[str] = None,
        type: Optional[str] = None,
        body: Optional[str] = None,
        priority: Optional[str] = None,
        status: Optional[str] = None,
        due_date: Optional[str] = None,
        owner_id: Optional[str] = None,
    ) -> Dict:
        """Helper function to create task properties dictionary.

        Args:
            subject: Task title
            type: Type of task (EMAIL, CALL, or TODO)
            body: Task notes/description
            priority: Priority level (LOW, MEDIUM, or HIGH)
            status: Status NOT_STARTED or COMPLETED
            due_date: Task due date in UTC format or Unix timestamp (ms)
            owner_id: ID of assigned user

        Returns:
            Dict containing task properties with non-None values
        """
        # Get current timestamp if not provided
        if not due_date:
            due_date = (
                datetime.now().replace(tzinfo=timezone.utc).strftime("%s") + "000"
            )

        properties = {
            "hs_task_subject": subject,
            "hs_task_type": type,
            "hs_task_body": body,
            "hs_task_status": status,
            "hs_task_priority": priority,
            "hs_timestamp": due_date,
            "hubspot_owner_id": owner_id,
        }

        # Filter out None values
        return {k: v for k, v in properties.items() if v is not None}

    def _create_task_associations(
        self,
        contact_ids: List[str] = [],
        company_ids: List[str] = [],
        deal_ids: List[str] = [],
    ) -> List[Dict]:
        """Helper function to create task associations.

        Args:
            contact_ids: List of contact IDs to associate with task
            company_ids: List of company IDs to associate with task
            deal_ids: List of deal IDs to associate with task

        Returns:
            List of association dictionaries
        """
        associations = []

        # Add contact associations
        for object_id in contact_ids:
            associations.append(
                {
                    "to": {"id": object_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 204,
                        }
                    ],
                }
            )

        # Add company associations
        for object_id in company_ids:
            associations.append(
                {
                    "to": {"id": object_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 192,
                        }
                    ],
                }
            )

        # Add deal associations
        for object_id in deal_ids:
            associations.append(
                {
                    "to": {"id": object_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 216,
                        }
                    ],
                }
            )

        return associations

    def create_task(
        self,
        subject: str,
        type: Optional[str] = "TODO",
        body: Optional[str] = None,
        priority: Optional[str] = "LOW",
        status: Optional[str] = "NOT_STARTED",
        due_date: Optional[str] = None,
        owner_id: Optional[str] = None,
        contact_ids: List[str] = [],
        company_ids: List[str] = [],
        deal_ids: List[str] = [],
    ) -> Dict:
        """Create a new task in HubSpot.

        Args:
            subject: Task title
            type: Type of task (EMAIL, CALL, or TODO). Defaults to TODO
            body: Task notes/description
            priority: Priority level (LOW, MEDIUM, or HIGH)
            status: Status NOT_STARTED or COMPLETED
            due_date: Task due date in UTC format or Unix timestamp (ms)
            owner_id: ID of assigned user
            contact_ids: List of contact IDs to associate with task
            company_ids: List of company IDs to associate with task
            deal_ids: List of deal IDs to associate with task

        Returns:
            Dict containing the created task data
        """
        # Build properties and associations using helper functions
        properties = self._create_task_properties(
            subject=subject,
            type=type,
            body=body,
            priority=priority,
            status=status,
            due_date=due_date,
            owner_id=owner_id,
        )

        associations = self._create_task_associations(
            contact_ids=contact_ids, company_ids=company_ids, deal_ids=deal_ids
        )

        data = {"properties": properties, "associations": associations}
        return self._make_request("POST", "/crm/v3/objects/tasks", data)

    def update_task(
        self,
        task_id: str,
        subject: str,
        type: Optional[str] = "TODO",
        body: Optional[str] = None,
        priority: Optional[str] = "LOW",
        status: Optional[str] = "NOT_STARTED",
        due_date: Optional[str] = None,
        owner_id: Optional[str] = None,
        contact_ids: List[str] = [],
        company_ids: List[str] = [],
        deal_ids: List[str] = [],
    ) -> Dict:
        """Update an existing task in HubSpot.

        Args:
            task_id: ID of the task to update
            subject: Task title
            type: Type of task (EMAIL, CALL, or TODO). Defaults to TODO
            body: Task notes/description
            priority: Priority level (LOW, MEDIUM, or HIGH)
            status: Status NOT_STARTED or COMPLETED
            due_date: Task due date in UTC format or Unix timestamp (ms)
            owner_id: ID of assigned user
            contact_ids: List of contact IDs to associate with task
            company_ids: List of company IDs to associate with task
            deal_ids: List of deal IDs to associate with task

        Returns:
            Dict containing the updated task data
        """
        # Extract values from properties dict
        task_properties = self._create_task_properties(
            subject=subject,
            type=type,
            body=body,
            priority=priority,
            status=status,
            due_date=due_date,
            owner_id=owner_id,
        )

        # Create associations
        associations = self._create_task_associations(
            contact_ids=contact_ids, company_ids=company_ids, deal_ids=deal_ids
        )

        data = {"properties": task_properties, "associations": associations}
        return self._make_request("PATCH", f"/crm/v3/objects/tasks/{task_id}", data)

    def delete_task(self, task_id: str) -> None:
        """Delete a task from HubSpot.

        This will move the task to the recycling bin in HubSpot, where it can be restored
        from the record timeline later if needed.

        Args:
            task_id (str): ID of the task to delete
        """
        self._make_request("DELETE", f"/crm/v3/objects/tasks/{task_id}")

    def create_note(
        self,
        body: str,
        deal_ids: List[str] = [],
        contact_ids: List[str] = [],
        company_ids: List[str] = [],
        hs_timestamp: Optional[int] = None,
        unique_id: Optional[int] = None,
    ) -> Dict:
        """Create a note with associations to contacts, deals, or companies.

        Args:
            body: Content of the note
            deal_ids: List of deal IDs to associate with the note
            contact_ids: List of contact IDs to associate with the note
            company_ids: List of company IDs to associate with the note
            hs_timestamp: Optional timestamp for the note (milliseconds since epoch)
            unique_id: Optional unique identifier for the note

        Returns:
            Dict containing the created note data
        """
        # Create timestamp if not provided
        if hs_timestamp is None:
            hs_timestamp = int(
                round(datetime.now().replace(tzinfo=pytz.utc).timestamp() * 1000, 0)
            )

        # Create associations
        associations = []
        for deal_id in deal_ids:
            associations.append(
                {
                    "to": {"id": deal_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 214,
                        }
                    ],
                }
            )
        for contact_id in contact_ids:
            associations.append(
                {
                    "to": {"id": contact_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 202,
                        }
                    ],
                }
            )
        for company_id in company_ids:
            associations.append(
                {
                    "to": {"id": company_id},
                    "types": [
                        {
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 190,
                        }
                    ],
                }
            )

        data = {
            "properties": {
                "hs_note_body": body,
                "hs_timestamp": hs_timestamp,
                "hs_unique_id": unique_id,
            },
            "associations": associations,
        }
        return self._make_request("POST", "/crm/v3/objects/notes", data=data)


def as_tools(configuration: HubSpotIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import List, Optional

    integration: HubSpotIntegration = HubSpotIntegration(configuration)

    class ListPropertiesSchema(BaseModel):
        object_type: str = Field(
            ...,
            description="Type of object to get properties for (contacts, companies, deals, tasks, notes)",
        )

    class GetAssociationsSchema(BaseModel):
        from_object_type: str = Field(
            ...,
            description="Type of the source objects (contacts, companies, deals, tasks, notes)",
        )
        object_ids: List[str] = Field(
            ..., description="List of source object IDs to get associations for"
        )
        to_object_type: str = Field(
            ..., description="Type of the target objects to get associations for"
        )
        after: Optional[str] = Field(None, description="Optional cursor for pagination")
        limit: Optional[int] = Field(
            100, description="Maximum number of results to return"
        )

    class ListContactsSchema(BaseModel):
        properties: Optional[List[str]] = Field(
            None, description="Optional list of contact properties to include"
        )
        limit: Optional[int] = Field(
            100, description="Maximum number of results to return"
        )

    class GetContactSchema(BaseModel):
        contact_id: Optional[str] = Field(
            None, description="ID of the HubSpot contact to retrieve"
        )
        email: Optional[str] = Field(
            None, description="Email address of the HubSpot contact to retrieve"
        )
        properties: Optional[List[str]] = Field(
            None, description="Optional list of contact properties to include"
        )
        associations: Optional[List[str]] = Field(
            None, description="Optional list of associations to include"
        )

    class CreateContactSchema(BaseModel):
        properties: Dict = Field(
            ..., description="Properties to create for the contact"
        )

    class UpdateContactSchema(BaseModel):
        contact_id: str = Field(..., description="ID of the HubSpot contact to update")
        properties: Dict = Field(
            ..., description="Properties to update for the contact"
        )

    class DeleteContactSchema(BaseModel):
        contact_id: str = Field(..., description="ID of the HubSpot contact to delete")

    class GetOwnersSchema(BaseModel):
        pass

    class PipelineStageSchema(BaseModel):
        pipeline: Optional[str] = Field(
            None, description="Optional pipeline name to filter by"
        )
        pipeline_id: Optional[str] = Field(
            None, description="Optional pipeline ID to filter by"
        )

    class ListDealsSchema(BaseModel):
        properties: Optional[List[str]] = Field(
            None, description="Optional list of deal properties to include"
        )
        limit: Optional[int] = Field(
            100, description="Maximum number of results to return"
        )

    class GetDealSchema(BaseModel):
        deal_id: str = Field(..., description="ID of the HubSpot deal to retrieve")
        properties: Optional[List[str]] = Field(
            None, description="Optional list of deal properties to include"
        )

    class CreateDealSchema(BaseModel):
        properties: Dict = Field(..., description="Properties to create for the deal")

    class UpdateDealSchema(BaseModel):
        deal_id: str = Field(..., description="ID of the HubSpot deal to update")
        properties: Dict = Field(..., description="Properties to update for the deal")

    class DeleteDealSchema(BaseModel):
        deal_id: str = Field(..., description="ID of the HubSpot deal to delete")

    class ListCompaniesSchema(BaseModel):
        properties: Optional[List[str]] = Field(
            None, description="Optional list of company properties to include"
        )
        limit: Optional[int] = Field(
            100, description="Maximum number of results to return"
        )

    class GetCompanySchema(BaseModel):
        company_id: str = Field(
            ..., description="ID of the HubSpot company to retrieve"
        )
        properties: Optional[List[str]] = Field(
            None, description="Optional list of company properties to include"
        )

    class CreateCompanySchema(BaseModel):
        properties: Dict = Field(
            ..., description="Properties to create for the company"
        )

    class UpdateCompanySchema(BaseModel):
        company_id: str = Field(..., description="ID of the HubSpot company to update")
        properties: Dict = Field(
            ..., description="Properties to update for the company"
        )

    class DeleteCompanySchema(BaseModel):
        company_id: str = Field(..., description="ID of the HubSpot company to delete")

    class ListTasksSchema(BaseModel):
        properties: Optional[List[str]] = Field(
            None, description="Optional list of task properties to include"
        )
        limit: Optional[int] = Field(
            100, description="Maximum number of results to return"
        )

    class GetTaskSchema(BaseModel):
        task_id: str = Field(..., description="ID of the task to retrieve")
        properties: Optional[List[str]] = Field(
            None, description="Optional list of task properties to include"
        )
        associations: Optional[List[str]] = Field(
            None, description="Optional list of associations to include"
        )

    class CreateTaskSchema(BaseModel):
        subject: str = Field(..., description="Task title")
        type: Optional[str] = Field(
            "TODO", description="Type of task (EMAIL, CALL, or TODO). Defaults to TODO"
        )
        body: Optional[str] = Field(None, description="Task notes/description")
        priority: Optional[str] = Field(
            "LOW", description="Priority level (LOW, MEDIUM, or HIGH)"
        )
        status: Optional[str] = Field(
            "NOT_STARTED", description="Status NOT_STARTED or COMPLETED"
        )
        due_date: Optional[int] = Field(
            None, description="Due date for the task (milliseconds since epoch)"
        )
        owner_id: Optional[str] = Field(None, description="ID of assigned user")
        contact_ids: List[str] = Field(
            ..., description="List of contact IDs to associate with the task"
        )
        company_ids: Optional[List[str]] = Field(
            None, description="Optional list of company IDs to associate with the task"
        )
        deal_ids: Optional[List[str]] = Field(
            None, description="Optional list of deal IDs to associate with the task"
        )

    class UpdateTaskSchema(BaseModel):
        task_id: str = Field(..., description="ID of the task to update")
        subject: str = Field(..., description="Task title")
        type: Optional[str] = Field(
            "TODO", description="Type of task (EMAIL, CALL, or TODO). Defaults to TODO"
        )
        body: Optional[str] = Field(None, description="Task notes/description")
        priority: Optional[str] = Field(
            "LOW", description="Priority level (LOW, MEDIUM, or HIGH)"
        )
        status: Optional[str] = Field(
            "NOT_STARTED", description="Status NOT_STARTED or COMPLETED"
        )
        due_date: Optional[int] = Field(
            None, description="Due date for the task (milliseconds since epoch)"
        )
        owner_id: Optional[str] = Field(None, description="ID of assigned user")
        contact_ids: List[str] = Field(
            ..., description="List of contact IDs to associate with the task"
        )
        company_ids: Optional[List[str]] = Field(
            None, description="Optional list of company IDs to associate with the task"
        )
        deal_ids: Optional[List[str]] = Field(
            None, description="Optional list of deal IDs to associate with the task"
        )

    class DeleteTaskSchema(BaseModel):
        task_id: str = Field(..., description="ID of the task to delete")

    class CreateNoteSchema(BaseModel):
        body: str = Field(..., description="Content of the note")
        deal_ids: List[str] = Field(
            default_factory=list,
            description="List of deal IDs to associate with the note",
        )
        contact_ids: List[str] = Field(
            ...,
            description="List of contact IDs to associate with the note. At least one contact ID is required.",
        )
        company_ids: List[str] = Field(
            default_factory=list,
            description="List of company IDs to associate with the note",
        )
        hs_timestamp: Optional[int] = Field(
            None,
            description="Optional timestamp for the note (milliseconds since epoch)",
        )
        unique_id: Optional[str] = Field(
            None, description="Optional unique identifier for the note"
        )

    return [
        StructuredTool(
            name="hubspot_list_properties",
            description="List properties of a specified HubSpot object type.",
            func=lambda object_type: integration.list_properties(object_type),
            args_schema=ListPropertiesSchema,
        ),
        StructuredTool(
            name="hubspot_get_associations",
            description="Get associations between objects in HubSpot.",
            func=lambda from_object_type,
            object_ids,
            to_object_type,
            after=None,
            limit=100: integration.get_associations(
                from_object_type, object_ids, to_object_type, after, limit
            ),
            args_schema=GetAssociationsSchema,
        ),
        StructuredTool(
            name="hubspot_list_contacts",
            description="Get all contacts from HubSpot with optional property filtering.",
            func=lambda properties=None, limit=100: integration.list_contacts(
                properties, limit
            ),
            args_schema=ListContactsSchema,
        ),
        StructuredTool(
            name="hubspot_get_contact",
            description="Get details about a HubSpot contact by their ID or email address.",
            func=lambda contact_id=None,
            email=None,
            properties=None,
            associations=None: integration.get_contact(
                contact_id, properties, associations
            )
            if contact_id
            else integration.get_contact_by_email(email, properties, associations),
            args_schema=GetContactSchema,
        ),
        StructuredTool(
            name="hubspot_create_contact",
            description="Create a new HubSpot contact.",
            func=lambda properties: integration.create_contact(properties),
            args_schema=CreateContactSchema,
        ),
        StructuredTool(
            name="hubspot_update_contact",
            description="Update an existing contact in HubSpot.",
            func=lambda contact_id, properties: integration.update_contact(
                contact_id, properties
            ),
            args_schema=UpdateContactSchema,
        ),
        StructuredTool(
            name="hubspot_delete_contact",
            description="Delete a contact in HubSpot.",
            func=lambda contact_id: integration.delete_contact(contact_id),
            args_schema=DeleteContactSchema,
        ),
        StructuredTool(
            name="hubspot_get_owners",
            description="Get all owners/users from HubSpot.",
            func=lambda: integration.get_owners(),
            args_schema=GetOwnersSchema,
        ),
        StructuredTool(
            name="hubspot_list_pipeline_stages",
            description="Get all pipeline stages or stages for a specific pipeline.",
            func=lambda pipeline=None,
            pipeline_id=None: integration.list_pipeline_stages(pipeline, pipeline_id),
            args_schema=PipelineStageSchema,
        ),
        StructuredTool(
            name="hubspot_list_deals",
            description="Get all deals from HubSpot with optional property filtering.",
            func=lambda properties=None, limit=100: integration.list_deals(
                properties, limit
            ),
            args_schema=ListDealsSchema,
        ),
        StructuredTool(
            name="hubspot_get_deal",
            description="Get a deal by its HubSpot ID.",
            func=lambda deal_id, properties=None: integration.get_deal(
                deal_id, properties
            ),
            args_schema=GetDealSchema,
        ),
        StructuredTool(
            name="hubspot_create_deal",
            description="Create a new deal in HubSpot.",
            func=lambda properties: integration.create_deal(properties),
            args_schema=CreateDealSchema,
        ),
        StructuredTool(
            name="hubspot_update_deal",
            description="Update an existing deal in HubSpot.",
            func=lambda deal_id, properties: integration.update_deal(
                deal_id, properties
            ),
            args_schema=UpdateDealSchema,
        ),
        StructuredTool(
            name="hubspot_delete_deal",
            description="Delete a deal in HubSpot.",
            func=lambda deal_id: integration.delete_deal(deal_id),
            args_schema=DeleteDealSchema,
        ),
        StructuredTool(
            name="hubspot_list_companies",
            description="Get all companies from HubSpot with optional property filtering.",
            func=lambda properties=None, limit=100: integration.list_companies(
                properties, limit
            ),
            args_schema=ListCompaniesSchema,
        ),
        StructuredTool(
            name="hubspot_get_company",
            description="Get a company by its HubSpot ID.",
            func=lambda company_id, properties=None: integration.get_company(
                company_id, properties
            ),
            args_schema=GetCompanySchema,
        ),
        StructuredTool(
            name="hubspot_create_company",
            description="Create a new company in HubSpot.",
            func=lambda properties: integration.create_company(properties),
            args_schema=CreateCompanySchema,
        ),
        StructuredTool(
            name="hubspot_update_company",
            description="Update an existing company in HubSpot.",
            func=lambda company_id, properties: integration.update_company(
                company_id, properties
            ),
            args_schema=UpdateCompanySchema,
        ),
        StructuredTool(
            name="hubspot_delete_company",
            description="Delete a company in HubSpot.",
            func=lambda company_id: integration.delete_company(company_id),
            args_schema=DeleteCompanySchema,
        ),
        StructuredTool(
            name="hubspot_list_tasks",
            description="Get all tasks from HubSpot with optional property filtering.",
            func=lambda properties=None, limit=100: integration.list_tasks(
                properties, limit
            ),
            args_schema=ListTasksSchema,
        ),
        StructuredTool(
            name="hubspot_get_task",
            description="Get a task by its HubSpot ID.",
            func=lambda **kwargs: integration.get_task(**kwargs),
            args_schema=GetTaskSchema,
        ),
        StructuredTool(
            name="hubspot_create_task",
            description="Create a task in HubSpot.",
            func=lambda **kwargs: integration.create_task(**kwargs),
            args_schema=CreateTaskSchema,
        ),
        StructuredTool(
            name="hubspot_update_task",
            description="Update a task in HubSpot.",
            func=lambda **kwargs: integration.update_task(**kwargs),
            args_schema=UpdateTaskSchema,
        ),
        StructuredTool(
            name="hubspot_delete_task",
            description="Delete a task in HubSpot.",
            func=lambda task_id: integration.delete_task(task_id),
            args_schema=DeleteTaskSchema,
        ),
        StructuredTool(
            name="hubspot_create_note",
            description="Create a note in HubSpot with associations to contacts, deals, or companies. If date is explicitly provided by user, convert it to milliseconds since epoch.",
            func=lambda **kwargs: integration.create_note(**kwargs),
            args_schema=CreateNoteSchema,
        ),
    ]
