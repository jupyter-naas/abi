from abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests

LOGO_URL = "https://logo.clearbit.com/harvestapp.com"


@dataclass
class HarvestIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Harvest integration.

    Attributes:
        access_token (str): Harvest API access token
        account_id (str): Harvest account ID
        base_url (str): Base URL for Harvest API. Defaults to "https://api.harvestapp.com/v2"
    """

    access_token: str
    account_id: str
    base_url: str = "https://api.harvestapp.com/v2"


class HarvestIntegration(Integration):
    """Harvest API integration client.

    This integration provides methods to interact with Harvest's API endpoints
    for time tracking and project management.
    """

    __configuration: HarvestIntegrationConfiguration

    def __init__(self, configuration: HarvestIntegrationConfiguration):
        """Initialize Harvest client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.access_token}",
            "Harvest-Account-ID": self.__configuration.account_id,
            "Content-Type": "application/json",
            "User-Agent": "HarvestIntegration",
        }

    def _make_request(
        self, endpoint: str, method: str = "GET", params: Dict = None, json: Dict = None
    ) -> Dict:
        """Make HTTP request to Harvest API.

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

        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, params=params, json=json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Harvest API request failed: {str(e)}")

    def get_time_entries(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> List[Dict]:
        """Get time entries with optional filters.

        Args:
            from_date (str, optional): Start date in YYYY-MM-DD format
            to_date (str, optional): End date in YYYY-MM-DD format
            user_id (str, optional): Filter by user ID

        Returns:
            List[Dict]: List of time entries
        """
        params = {}
        if from_date:
            params["from"] = from_date
        if to_date:
            params["to"] = to_date
        if user_id:
            params["user_id"] = user_id

        response = self._make_request("/time_entries", params=params)
        return response.get("time_entries", [])

    def get_projects(self, is_active: bool = True) -> List[Dict]:
        """Get list of projects.

        Args:
            is_active (bool, optional): Filter for active projects. Defaults to True.

        Returns:
            List[Dict]: List of projects
        """
        params = {"is_active": str(is_active).lower()}
        response = self._make_request("/projects", params=params)
        return response.get("projects", [])

    def get_clients(self, is_active: bool = True) -> List[Dict]:
        """Get list of clients.

        Args:
            is_active (bool, optional): Filter for active clients. Defaults to True.

        Returns:
            List[Dict]: List of clients
        """
        params = {"is_active": str(is_active).lower()}
        response = self._make_request("/clients", params=params)
        return response.get("clients", [])

    def get_users(self, is_active: bool = True) -> List[Dict]:
        """Get list of users.

        Args:
            is_active (bool, optional): Filter for active users. Defaults to True.

        Returns:
            List[Dict]: List of users
        """
        params = {"is_active": str(is_active).lower()}
        response = self._make_request("/users", params=params)
        return response.get("users", [])

    def create_time_entry(
        self,
        project_id: str,
        task_id: str,
        spent_date: str,
        hours: float,
        notes: Optional[str] = None,
    ) -> Dict:
        """Create a new time entry.

        Args:
            project_id (str): Project ID
            task_id (str): Task ID
            spent_date (str): Date in YYYY-MM-DD format
            hours (float): Hours spent
            notes (str, optional): Notes for the time entry

        Returns:
            Dict: Created time entry data
        """
        payload = {
            "project_id": project_id,
            "task_id": task_id,
            "spent_date": spent_date,
            "hours": hours,
        }
        if notes:
            payload["notes"] = notes

        return self._make_request("/time_entries", method="POST", json=payload)


def as_tools(configuration: HarvestIntegrationConfiguration):
    """Convert Harvest integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = HarvestIntegration(configuration)

    class TimeEntriesSchema(BaseModel):
        from_date: Optional[str] = Field(
            None, description="Start date in YYYY-MM-DD format"
        )
        to_date: Optional[str] = Field(
            None, description="End date in YYYY-MM-DD format"
        )
        user_id: Optional[str] = Field(None, description="Filter by user ID")

    class ActiveFilterSchema(BaseModel):
        is_active: bool = Field(default=True, description="Filter for active items")

    class CreateTimeEntrySchema(BaseModel):
        project_id: str = Field(..., description="Project ID")
        task_id: str = Field(..., description="Task ID")
        spent_date: str = Field(..., description="Date in YYYY-MM-DD format")
        hours: float = Field(..., description="Hours spent")
        notes: Optional[str] = Field(None, description="Notes for the time entry")

    return [
        StructuredTool(
            name="harvest_get_time_entries",
            description="Get time entries with optional filters",
            func=lambda from_date, to_date, user_id: integration.get_time_entries(
                from_date, to_date, user_id
            ),
            args_schema=TimeEntriesSchema,
        ),
        StructuredTool(
            name="harvest_get_projects",
            description="Get list of projects",
            func=lambda is_active: integration.get_projects(is_active),
            args_schema=ActiveFilterSchema,
        ),
        StructuredTool(
            name="harvest_get_clients",
            description="Get list of clients",
            func=lambda is_active: integration.get_clients(is_active),
            args_schema=ActiveFilterSchema,
        ),
        StructuredTool(
            name="harvest_get_users",
            description="Get list of users",
            func=lambda is_active: integration.get_users(is_active),
            args_schema=ActiveFilterSchema,
        ),
        StructuredTool(
            name="harvest_create_time_entry",
            description="Create a new time entry",
            func=lambda project_id,
            task_id,
            spent_date,
            hours,
            notes: integration.create_time_entry(
                project_id, task_id, spent_date, hours, notes
            ),
            args_schema=CreateTimeEntrySchema,
        ),
    ]
