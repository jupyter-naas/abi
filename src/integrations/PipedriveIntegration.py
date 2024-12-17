from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests

@dataclass
class PipedriveIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Pipedrive integration.
    
    Attributes:
        api_token (str): Pipedrive API token
        base_url (str): Base URL for Pipedrive API. Defaults to "https://api.pipedrive.com/v1"
    """
    api_token: str
    base_url: str = "https://api.pipedrive.com/v1"

class PipedriveIntegration(Integration):
    """Pipedrive API integration client.
    
    This class provides methods to interact with Pipedrive's API endpoints
    for CRM and sales pipeline management.
    """

    __configuration: PipedriveIntegrationConfiguration

    def __init__(self, configuration: PipedriveIntegrationConfiguration):
        """Initialize Pipedrive client with API token."""
        super().__init__(configuration)
        self.__configuration = configuration

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, json: Dict = None) -> Dict:
        """Make HTTP request to Pipedrive API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            params (Dict, optional): Query parameters. Defaults to None.
            json (Dict, optional): JSON body for POST requests. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        
        # Add API token to params
        params = params or {}
        params["api_token"] = self.__configuration.api_token
        
        try:
            response = requests.request(
                method=method,
                url=url,
                params=params,
                json=json
            )
            response.raise_for_status()
            data = response.json()
            
            if not data.get("success", False):
                raise IntegrationConnectionError(f"Pipedrive API error: {data.get('error', 'Unknown error')}")
                
            return data.get("data", {})
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Pipedrive API request failed: {str(e)}")

    def get_deals(self, status: Optional[str] = None) -> List[Dict]:
        """Get list of deals.
        
        Args:
            status (str, optional): Filter by deal status
            
        Returns:
            List[Dict]: List of deals
        """
        params = {}
        if status:
            params["status"] = status
            
        return self._make_request("/deals", params=params)

    def get_deal(self, deal_id: int) -> Dict:
        """Get deal details.
        
        Args:
            deal_id (int): Deal ID
            
        Returns:
            Dict: Deal details
        """
        return self._make_request(f"/deals/{deal_id}")

    def get_persons(self, search_term: Optional[str] = None) -> List[Dict]:
        """Get list of persons.
        
        Args:
            search_term (str, optional): Search term to filter persons
            
        Returns:
            List[Dict]: List of persons
        """
        params = {}
        if search_term:
            params["term"] = search_term
            
        return self._make_request("/persons", params=params)

    def get_organizations(self, search_term: Optional[str] = None) -> List[Dict]:
        """Get list of organizations.
        
        Args:
            search_term (str, optional): Search term to filter organizations
            
        Returns:
            List[Dict]: List of organizations
        """
        params = {}
        if search_term:
            params["term"] = search_term
            
        return self._make_request("/organizations", params=params)

    def create_deal(self, 
                   title: str,
                   value: Optional[float] = None,
                   currency: str = "EUR",
                   person_id: Optional[int] = None,
                   org_id: Optional[int] = None) -> Dict:
        """Create a new deal.
        
        Args:
            title (str): Deal title
            value (float, optional): Deal value
            currency (str, optional): Deal currency. Defaults to "EUR"
            person_id (int, optional): Associated person ID
            org_id (int, optional): Associated organization ID
            
        Returns:
            Dict: Created deal data
        """
        payload = {"title": title}
        
        if value is not None:
            payload["value"] = value
            payload["currency"] = currency
        if person_id:
            payload["person_id"] = person_id
        if org_id:
            payload["org_id"] = org_id
            
        return self._make_request("/deals", method="POST", json=payload)

def as_tools(configuration: PipedriveIntegrationConfiguration):
    """Convert Pipedrive integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = PipedriveIntegration(configuration)
    
    class DealsSchema(BaseModel):
        status: Optional[str] = Field(None, description="Filter by deal status")

    class DealSchema(BaseModel):
        deal_id: int = Field(..., description="Deal ID")

    class SearchSchema(BaseModel):
        search_term: Optional[str] = Field(None, description="Search term")

    class CreateDealSchema(BaseModel):
        title: str = Field(..., description="Deal title")
        value: Optional[float] = Field(None, description="Deal value")
        currency: str = Field(default="EUR", description="Deal currency")
        person_id: Optional[int] = Field(None, description="Associated person ID")
        org_id: Optional[int] = Field(None, description="Associated organization ID")
    
    return [
        StructuredTool(
            name="get_pipedrive_deals",
            description="Get list of deals with optional status filter",
            func=lambda status: integration.get_deals(status),
            args_schema=DealsSchema
        ),
        StructuredTool(
            name="get_pipedrive_deal",
            description="Get deal details by ID",
            func=lambda deal_id: integration.get_deal(deal_id),
            args_schema=DealSchema
        ),
        StructuredTool(
            name="get_pipedrive_persons",
            description="Get list of persons with optional search term",
            func=lambda search_term: integration.get_persons(search_term),
            args_schema=SearchSchema
        ),
        StructuredTool(
            name="get_pipedrive_organizations",
            description="Get list of organizations with optional search term",
            func=lambda search_term: integration.get_organizations(search_term),
            args_schema=SearchSchema
        ),
        StructuredTool(
            name="create_pipedrive_deal",
            description="Create a new deal",
            func=lambda title, value, currency, person_id, org_id: integration.create_deal(
                title, value, currency, person_id, org_id
            ),
            args_schema=CreateDealSchema
        )
    ] 