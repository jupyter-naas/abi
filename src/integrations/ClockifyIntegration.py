from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from datetime import datetime

LOGO_URL = "https://logo.clearbit.com/clockify.me"

@dataclass
class ClockifyIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Clockify integration.
    
    Attributes:
        api_key (str): Clockify API key for authentication
        base_url (str): Base URL for Clockify API. Defaults to "https://api.clockify.me/api/v1"
    """
    api_key: str
    base_url: str = "https://api.clockify.me/api/v1"

class ClockifyIntegration(Integration):
    """Clockify API integration client.
    
    This class provides methods to interact with Clockify's API endpoints.
    It handles authentication and request management.
    """

    __configuration: ClockifyIntegrationConfiguration

    def __init__(self, configuration: ClockifyIntegrationConfiguration):
        """Initialize Clockify client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "X-Api-Key": self.__configuration.api_key,
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, params: Dict = None) -> Dict:
        """Make HTTP request to Clockify API.
        
        Args:
            method (str): HTTP method (GET, POST, etc.)
            endpoint (str): API endpoint
            params (Dict, optional): Query parameters. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Clockify API request failed: {str(e)}")

    def get_workspaces(self) -> List[Dict]:
        """Retrieve all workspaces for the authenticated user.
        
        Returns:
            List[Dict]: List of workspace data
            
        Raises:
            IntegrationConnectionError: If the workspace retrieval fails
        """
        return self._make_request("GET", "/workspaces")

    def get_users(self, workspace_id: str) -> List[Dict]:
        """Retrieve all users in a workspace.
        
        Args:
            workspace_id (str): The ID of the workspace
            
        Returns:
            List[Dict]: List of user data
            
        Raises:
            IntegrationConnectionError: If the users retrieval fails
        """
        return self._make_request("GET", f"/workspaces/{workspace_id}/users")

    def get_projects(self, workspace_id: str) -> List[Dict]:
        """Retrieve all projects in a workspace.
        
        Args:
            workspace_id (str): The ID of the workspace
            
        Returns:
            List[Dict]: List of project data
            
        Raises:
            IntegrationConnectionError: If the projects retrieval fails
        """
        return self._make_request("GET", f"/workspaces/{workspace_id}/projects")

    def get_time_entries(self, workspace_id: str, user_id: str, start_date: str = None, end_date: str = None) -> List[Dict]:
        """Retrieve all time entries for a user in a workspace.
        
        Args:
            workspace_id (str): The ID of the workspace
            user_id (str): The ID of the user
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            List[Dict]: List of time entry data
            
        Raises:
            IntegrationConnectionError: If the time entries retrieval fails
        """
        params = {}
        if start_date:
            # Convert start_date to ISO format with timezone and ensure Z at the end
            start_datetime = datetime.strptime(start_date, "%Y-%m-%d").replace(hour=0, minute=0, second=0)
            params["start"] = start_datetime.isoformat() + "Z"
        if end_date:
            # Convert end_date to ISO format with timezone and ensure Z at the end
            end_datetime = datetime.strptime(end_date, "%Y-%m-%d").replace(hour=23, minute=59, second=59)
            params["end"] = end_datetime.isoformat() + "Z"
        
        all_entries = []
        page = 1
        
        while True:
            params.update({
                "page": page,
                "page-size": 100
            })
            
            entries = self._make_request(
                "GET",
                f"/workspaces/{workspace_id}/user/{user_id}/time-entries",
                params=params
            )
            
            if not entries:
                break
            
            all_entries.extend(entries)
            page += 1
        
        return all_entries

def as_tools(configuration: ClockifyIntegrationConfiguration):
    """Convert Clockify integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = ClockifyIntegration(configuration)
    
    class WorkspaceSchema(BaseModel):
        pass

    class UserSchema(BaseModel):
        workspace_id: str = Field(..., description="Clockify workspace ID")

    class ProjectSchema(BaseModel):
        workspace_id: str = Field(..., description="Clockify workspace ID")
        
    class TimeEntriesSchema(BaseModel):
        workspace_id: str = Field(..., description="Clockify workspace ID")
        user_id: str = Field(..., description="Clockify user ID")
        start_date: Optional[str] = Field(..., description="Start date in YYYY-MM-DD format")
        end_date: Optional[str] = Field(..., description="End date in YYYY-MM-DD format")
    
    return [
        StructuredTool(
            name="get_clockify_workspaces",
            description="Retrieve all workspaces for the authenticated user",
            func=lambda: integration.get_workspaces(),
            args_schema=WorkspaceSchema
        ),
        StructuredTool(
            name="get_clockify_users",
            description="Retrieve all users in a workspace",
            func=lambda workspace_id: integration.get_users(workspace_id),
            args_schema=UserSchema
        ),
        StructuredTool(
            name="get_clockify_projects",
            description="Retrieve all projects in a workspace",
            func=lambda workspace_id: integration.get_projects(workspace_id),
            args_schema=ProjectSchema
        ),
        StructuredTool(
            name="get_clockify_time_entries",
            description="Retrieve all time entries for a user in a workspace",
            func=lambda workspace_id, user_id, start_date, end_date: integration.get_time_entries(workspace_id, user_id, start_date, end_date),
            args_schema=TimeEntriesSchema
        )
    ]