from typing import Dict, List, Optional
from dataclasses import dataclass
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
import requests
from datetime import datetime
import pandas as pd
import pytz

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
    __configuration: HubSpotIntegrationConfiguration

    def __init__(self, configuration: HubSpotIntegrationConfiguration):
        """Initialize HubSpot client with access token."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        # Test connection
        try:
            self._make_request("GET", "/crm/v3/objects/contacts")
        except Exception as e:
            raise IntegrationConnectionError(f"Failed to connect to HubSpot: {str(e)}")

    def _make_request(self, method: str, endpoint: str, data: Dict = None, params: Dict = None) -> Dict:
        """Make HTTP request to HubSpot API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=data,
                params=params
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"HubSpot API request failed: {str(e)}")
        
    def get_all(self, endpoint: str, hs_properties: Optional[List[str]] = None) -> pd.DataFrame:
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
        df = pd.DataFrame(items).reset_index(drop=True)
        params.pop("after", None)
        if hs_properties:
            params.pop("properties", None)
        return df

    def create_contact(self, properties: Dict) -> Dict:
        """Create a new contact in HubSpot."""
        data = {"properties": properties}
        return self._make_request("POST", "/crm/v3/objects/contacts", data)
    
    def get_contacts(self, properties: Optional[List[str]] = None) -> pd.DataFrame:
        """Get all contacts from HubSpot with optional property filtering.
        
        Args:
            properties: Optional list of contact properties to include. If None, includes all properties.
            
        Returns:
            DataFrame containing all contacts with specified properties.
        """
        return self.get_all("/crm/v3/objects/contacts", properties)
    
    def get_contact(self, contact_id: str, properties: Optional[List[str]] = None, associations: Optional[List[str]] = None) -> Dict:
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
            
        return self._make_request("GET", f"/crm/v3/objects/contacts/{contact_id}", params=params)

    def get_contact_by_email(self, email: str, properties: Optional[List[str]] = None, associations: Optional[List[str]] = None) -> Dict:
        """Get a contact by email address.
        
        Args:
            email: Email address of the contact
            properties: Optional list of contact properties to include
            associations: Optional list of associations to include
            
        Returns:
            Dict containing the contact data
        """
        params = {
            "idProperty": "email"
        }
        if properties:
            params["properties"] = ",".join(properties)
        if associations:
            params["associations"] = ",".join(associations)
            
        return self._make_request("GET", f"/crm/v3/objects/contacts/{email}", params=params)

    def update_contact(self, contact_id: str, properties: Dict) -> Dict:
        """Update an existing contact in HubSpot."""
        data = {"properties": properties}
        return self._make_request("PATCH", f"/crm/v3/objects/contacts/{contact_id}", data)

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
            hs_timestamp = int(round(datetime.now().replace(tzinfo=pytz.utc).timestamp() * 1000, 0))

        # Create associations
        associations = []
        for deal_id in deal_ids:
            associations.append({
                "to": {"id": deal_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 214
                }]
            })
        for contact_id in contact_ids:
            associations.append({
                "to": {"id": contact_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 202
                }]
            })
        for company_id in company_ids:
            associations.append({
                "to": {"id": company_id},
                "types": [{
                    "associationCategory": "HUBSPOT_DEFINED",
                    "associationTypeId": 190
                }]
            })

        data = {
            "properties":
            {
                "hs_note_body": body,
                "hs_timestamp": hs_timestamp,
                "hs_unique_id": unique_id
            },
            "associations": associations
        }
        return self._make_request("POST", "/crm/v3/objects/notes", data=data)
    
    def get_deals(self, properties: Optional[List[str]] = None) -> pd.DataFrame:
        """Get all deals from HubSpot with optional property filtering.
        
        Args:
            properties: Optional list of deal properties to include. If None, includes all properties.
            
        Returns:
            DataFrame containing all deals with specified properties.
        """
        return self.get_all("/crm/v3/objects/deals", properties)

    def get_companies(self, properties: Optional[List[str]] = None) -> pd.DataFrame:
        """Get all companies from HubSpot with optional property filtering.
        
        Args:
            properties: Optional list of company properties to include. If None, includes all properties.
            
        Returns:
            DataFrame containing all companies with specified properties.
        """
        return self.get_all("/crm/v3/objects/companies", properties)
    
    def get_pipeline_stages(self, pipeline: Optional[str] = None, pipeline_id: Optional[str] = None) -> pd.DataFrame:
        """Get all pipeline stages or stages for a specific pipeline.
        
        Args:
            pipeline: Optional pipeline name to filter by
            pipeline_id: Optional pipeline ID to filter by
            
        Returns:
            DataFrame containing pipeline stages with columns:
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
                    "archived": stage.get("archived")
                }
                deal_stages.append(deal_stage)

        # Create DataFrame
        df = pd.DataFrame(deal_stages)
        
        # Convert timestamps
        df.createdAt = pd.to_datetime(df.createdAt).dt.strftime("%Y-%m-%d %H:%M:%S")
        df.updatedAt = pd.to_datetime(df.updatedAt).dt.strftime("%Y-%m-%d %H:%M:%S")

        # Filter if pipeline name or ID provided
        if pipeline is not None:
            df = df[df.pipeline == str(pipeline)]
        if pipeline_id is not None:
            df = df[df.pipeline_id == str(pipeline_id)]

        # Sort and reset index
        df = df.sort_values(by=["pipeline", "displayOrder"])
        df = df.reset_index(drop=True)
        
        return df

    def list_properties(self, object_type: str) -> List[Dict]:
        """List properties of a specified HubSpot object type."""
        valid_types = ["contacts", "companies", "deals"]
        if object_type not in valid_types:
            raise ValueError(f"Invalid object type. Must be one of: {', '.join(valid_types)}")

        url = f"{self.__configuration.base_url}/crm/v3/properties/{object_type}"
        response = requests.get(url, headers=self.headers)

        if response.status_code == 200:
            properties_data = response.json()
            properties = properties_data['results']
            for prop in properties:
                prop_name = prop['name']
                prop_label = prop['label']
                print(f"Property Name: {prop_name}")
                print(f"Property Label: {prop_label}")
                print()
            return properties
        else:
            print(f"Failed to retrieve properties. Status code: {response.status_code}")
            print(response.json())
            return []

    def search_objects(self, object_type: str, query: str, properties: Optional[List[str]] = None, limit: int = 100) -> pd.DataFrame:
        """Search for objects in HubSpot using the Search API.
        
        Args:
            object_type: Type of object to search for (contacts, companies, deals)
            query: Search query string
            properties: Optional list of properties to include in results
            limit: Maximum number of results to return (default: 100)
            
        Returns:
            DataFrame containing search results with specified properties
        """
        valid_types = ["contacts", "companies", "deals"]
        if object_type not in valid_types:
            raise ValueError(f"Invalid object type. Must be one of: {', '.join(valid_types)}")
        
        data = {
            "query": query,
            "limit": limit
        }
        if properties:
            data["properties"] = properties
        
        results = self._make_request("POST", f"/crm/v3/objects/{object_type}/search", data=data)
        
        items = []
        for row in results.get("results", []):
            properties = row.get("properties", {})
            properties["id"] = row.get("id")
            items.append(properties)
        
        return pd.DataFrame(items).reset_index(drop=True)

    def get_associations(self, from_object_type: str, object_ids: List[str], to_object_type: str, after: Optional[str] = None, limit: Optional[int] = 100) -> Dict:
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

def as_tools(configuration: HubSpotIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    from typing import List, Optional
    
    integration : HubSpotIntegration = HubSpotIntegration(configuration)

    class GetContactSchema(BaseModel):
        contact_id: Optional[str] = Field(None, description="ID of the HubSpot contact to retrieve")
        email: Optional[str] = Field(None, description="Email address of the HubSpot contact to retrieve")
        properties: Optional[List[str]] = Field(None, description="Optional list of contact properties to include")
        associations: Optional[List[str]] = Field(None, description="Optional list of associations to include")

    class UpdateContactSchema(BaseModel):
        contact_id: str = Field(..., description="ID of the HubSpot contact to update")
        properties: Dict = Field(..., description="Properties to update for the contact")

    class CreateNoteSchema(BaseModel):
        body: str = Field(..., description="Content of the note")
        deal_ids: Optional[List[str]] = Field(..., description="Optional list of deal IDs to associate with the note")
        contact_ids: List[str] = Field(..., description="List of contact IDs to associate with the note. At least one contact ID is required.")
        company_ids: Optional[List[str]] = Field(..., description="Optional list of company IDs to associate with the note")
        hs_timestamp: Optional[int] = Field(..., description="Optional timestamp for the note (milliseconds since epoch)")
        unique_id: Optional[str] = Field(..., description="Optional unique identifier for the note")

    class SearchObjectsSchema(BaseModel):
        object_type: str = Field(..., description="Type of HubSpot object to search for (contacts, companies, deals)")
        query: str = Field(..., description="Search query string")
        properties: Optional[List[str]] = Field(None, description="Optional list of properties to include in results")
        limit: Optional[int] = Field(100, description="Maximum number of results to return")

    return [
        StructuredTool(
            name="get_hubspot_contact",
            description="Get details about a HubSpot contact by their ID or email address.",
            func=lambda contact_id=None, email=None, properties=None, associations=None: 
                integration.get_contact(contact_id, properties, associations) if contact_id else 
                integration.get_contact_by_email(email, properties, associations),
            args_schema=GetContactSchema
        ),
        StructuredTool(
            name="update_hubspot_contact",
            description="Update an existing contact in HubSpot.",
            func=integration.update_contact,
            args_schema=UpdateContactSchema
        ),
        StructuredTool(
            name="create_hubspot_note",
            description="Create a note in HubSpot with associations to contacts, deals, or companies. If date is explicitly provided by user, convert it to milliseconds since epoch.",
            func=lambda body, deal_ids=[], contact_ids=[], company_ids=[], hs_timestamp=None, unique_id=None: integration.create_note(body, deal_ids, contact_ids, company_ids, hs_timestamp, unique_id),
            args_schema=CreateNoteSchema
        ),
        StructuredTool(
            name="search_hubspot_objects",
            description="Search for objects in HubSpot using the Search API.",
            func=integration.search_objects,
            args_schema=SearchObjectsSchema
        )
    ]
