from typing import Dict
from abi.integration.integration import (
    Integration,
    IntegrationConnectionError,
    IntegrationConfiguration,
)
from dataclasses import dataclass
from pydantic import BaseModel, Field
import requests

LOGO_URL = "https://logo.clearbit.com/microsoft.com"


@dataclass
class OneDriveIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for OneDrive integration.

    Attributes:
        access_token (str): OneDrive OAuth access token
        base_url (str): Base URL for Microsoft Graph API
    """

    access_token: str
    base_url: str = "https://graph.microsoft.com/v1.0"


class OneDriveIntegration(Integration):
    """OneDrive integration class for interacting with Microsoft OneDrive.

    This integration provides methods to interact with OneDrive's API endpoints.
    """

    __configuration: OneDriveIntegrationConfiguration

    def __init__(self, configuration: OneDriveIntegrationConfiguration):
        """Initialize OneDrive client with access token."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Content-Type": "application/json",
        }

        self.base_url = self.__configuration.base_url

    def _make_request(
        self, method: str, endpoint: str, data: Dict = None, params: Dict = None
    ) -> Dict:
        """Make HTTP request to Microsoft Graph API."""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, json=data, params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"OneDrive API request failed: {str(e)}")

    def list_files(self, folder_path: str = "/") -> Dict:
        """List files and folders in the specified OneDrive folder.

        Args:
            folder_path (str): Path to the folder. Defaults to root folder.

        Returns:
            Dict: Dictionary containing file and folder information
        """
        endpoint = "/me/drive/root/children"
        if folder_path != "/":
            endpoint = f"/me/drive/root:/{folder_path}:/children"
        return self._make_request("GET", endpoint)

    def get_file_details(self, file_id: str) -> Dict:
        """Get details of a specific file.

        Args:
            file_id (str): ID of the file

        Returns:
            Dict: File details
        """
        endpoint = f"/me/drive/items/{file_id}"
        return self._make_request("GET", endpoint)

    def search_files(self, query: str) -> Dict:
        """Search for files and folders.

        Args:
            query (str): Search query string

        Returns:
            Dict: Search results
        """
        endpoint = f"/me/drive/root/search(q='{query}')"
        return self._make_request("GET", endpoint)


def as_tools(configuration: OneDriveIntegrationConfiguration):
    """Returns a list of LangChain tools for OneDrive integration.

    Args:
        configuration (OneDriveIntegrationConfiguration): Configuration for OneDrive integration

    Returns:
        list[StructuredTool]: List of LangChain tools
    """
    from langchain_core.tools import StructuredTool

    integration = OneDriveIntegration(configuration)

    class ListFilesSchema(BaseModel):
        folder_path: str = Field(
            default="/",
            description="Path to the folder to list files from. Defaults to root folder",
        )

    class GetFileDetailsSchema(BaseModel):
        file_id: str = Field(..., description="ID of the file to get details for")

    class SearchFilesSchema(BaseModel):
        query: str = Field(
            ..., description="Search query string to find files and folders"
        )

    return [
        StructuredTool(
            name="onedrive_list_files",
            description="List files and folders in the specified OneDrive folder",
            func=lambda folder_path: integration.list_files(folder_path),
            args_schema=ListFilesSchema,
        ),
        StructuredTool(
            name="onedrive_get_file_details",
            description="Get details of a specific file in OneDrive",
            func=lambda file_id: integration.get_file_details(file_id),
            args_schema=GetFileDetailsSchema,
        ),
        StructuredTool(
            name="onedrive_search_files",
            description="Search for files and folders in OneDrive",
            func=lambda query: integration.search_files(query),
            args_schema=SearchFilesSchema,
        ),
    ]
