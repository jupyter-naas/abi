from typing import Dict, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field
from abi.integration.integration import (
    Integration,
    IntegrationConnectionError,
    IntegrationConfiguration,
)
from src import config
import requests

@dataclass
class AiaIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for AIA integration.

    Attributes:
        api_key (str): AIA API key for authentication
        base_url (str): Base URL for AIA API
    """
    api_key: str
    li_at: str
    JSESSIONID: str
    base_url: str = (
        "https://naas-abi-space.default.space.naas.ai"  # Replace with actual base URL
    )


class AiaIntegration(Integration):
    """AIA integration client.

    This integration provides methods to interact with AIA's API endpoints.
    """

    __configuration: AiaIntegrationConfiguration

    def __init__(self, configuration: AiaIntegrationConfiguration):
        """Initialize AIA client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration

    def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """Make HTTP request to AIA API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(method=method, url=url, json=data)
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"AIA API request failed: {str(e)}")

    def create_aia(self, linkedin_urls: List[str]) -> Dict:
        """Create an AIA organization with the specified parameters."""
        data = {
            "api_key": self.__configuration.api_key,
            "workspace_id": config.workspace_id,
            "linkedin_urls": linkedin_urls,
            "li_at": self.__configuration.li_at,
            "JSESSIONID": self.__configuration.JSESSIONID,
        }
        return self._make_request("POST", "/ontology/create_aia_organization", data)


def as_tools(configuration: AiaIntegrationConfiguration):
    from langchain_core.tools import StructuredTool

    integration: AiaIntegration = AiaIntegration(configuration)

    class CreateAiaOrganizationSchema(BaseModel):
        linkedin_urls: List[str] = Field(
            ...,
            description=r"LinkedIn URL(s) to process. It can be one or multiple URLs. URLs must be in the format: https://.+\.linkedin\.[^/]+/in/[^?]+",
        )

    return [
        StructuredTool(
            name="aia_create_personal_agent",
            description="Create AIA Personal Assistant/Agent based on LinkedIn URL.",
            func=lambda linkedin_urls: integration.create_aia(linkedin_urls),
            args_schema=CreateAiaOrganizationSchema,
        )
    ]
