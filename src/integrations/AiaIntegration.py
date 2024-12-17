from typing import Dict, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration
from src import secret
import requests

LOGO_URL = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_AIA.png"

@dataclass
class AiaIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for AIA integration.
    
    Attributes:
        api_key (str): AIA API key for authentication
        base_url (str): Base URL for AIA API
    """
    api_key: str
    base_url: str = "https://naas-abi-space.default.nebari.dev.naas.ai"  # Replace with actual base URL

class AiaIntegration(Integration):
    
    __configuration: AiaIntegrationConfiguration
    
    def __init__(self, configuration: AiaIntegrationConfiguration):
        """Initialize AIA client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration

    def _make_request(self, method: str, endpoint: str, data: Dict = None) -> Dict:
        """Make HTTP request to AIA API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"AIA API request failed: {str(e)}")

    def create_aia(self, workspace_id: str, linkedin_urls: List[str]) -> Dict:
        """Create an AIA organization with the specified parameters."""
        data = {
            "api_key": self.__configuration.api_key,
            "workspace_id": workspace_id,
            "linkedin_urls": linkedin_urls,
            "li_at": secret.get('li_at'),
            "JSESSIONID": secret.get('jsessionid'),
        }
        return self._make_request("POST", "/ontology/create_aia_organization", data)

def as_tools(configuration: AiaIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration: AiaIntegration = AiaIntegration(configuration)

    class CreateAiaOrganizationSchema(BaseModel):
        workspace_id: str = Field(..., description="Workspace ID for the organization")
        linkedin_urls: List[str] = Field(..., description="List of LinkedIn URLs to process")
    
    return [
        StructuredTool(
            name="create_aia",
            description="Create AIA assistant and ontology with LinkedIn data to naas workspace",
            func=lambda workspace_id, linkedin_urls: 
                integration.create_aia(workspace_id, linkedin_urls),
            args_schema=CreateAiaOrganizationSchema
        )
    ]