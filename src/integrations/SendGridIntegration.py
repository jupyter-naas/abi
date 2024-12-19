from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
import os
import time

LOGO_URL = "https://logo.clearbit.com/sendgrid.com"

@dataclass
class SendGridIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for SendGrid integration.
    
    Attributes:
        api_key (str): SendGrid API key
        base_url (str): Base URL for SendGrid API. Defaults to "https://api.sendgrid.com/v3"
    """
    api_key: str
    base_url: str = "https://api.sendgrid.com/v3"

class SendGridIntegration(Integration):
    """SendGrid API integration client.
    
    This integration provides methods to interact with SendGrid's API endpoints
    for managing contacts, lists, and unsubscribes.
    """

    __configuration: SendGridIntegrationConfiguration

    def __init__(self, configuration: SendGridIntegrationConfiguration):
        """Initialize SendGrid client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, method: str, endpoint: str, json: Dict = None) -> Dict:
        """Make HTTP request to SendGrid API.
        
        Args:
            method (str): HTTP method (GET, POST, PUT, DELETE)
            endpoint (str): API endpoint
            json (Dict, optional): JSON body for request
            
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
                json=json
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"SendGrid API request failed: {str(e)}")

    def create_contacts(self, contacts: List[Dict], list_ids: List[str], wait: bool = True) -> Dict:
        """Create or update contacts and add them to specified lists.
        
        Args:
            contacts (List[Dict]): List of contact data dictionaries
            list_ids (List[str]): List of list IDs to add contacts to
            wait (bool, optional): Wait for job completion. Defaults to True.
            
        Returns:
            Dict: Job status response
        """
        data = {
            "list_ids": list_ids,
            "contacts": contacts
        }
        response = self._make_request("PUT", "/marketing/contacts", data)
        
        if wait and "job_id" in response:
            return self._wait_for_job(response["job_id"])
        return response

    def _wait_for_job(self, job_id: str, max_retry: int = 20) -> Dict:
        """Wait for a job to complete.
        
        Args:
            job_id (str): Job ID to check
            max_retry (int, optional): Maximum number of retries. Defaults to 20.
            
        Returns:
            Dict: Final job status
        """
        retry = 0
        while retry < max_retry:
            result = self._make_request("GET", f"/marketing/contacts/imports/{job_id}")
            if result.get("status") == "completed":
                return result
            time.sleep(15)
            retry += 1
        return result

    def search_contacts(self, query: Optional[str] = None, email: Optional[str] = None) -> Dict:
        """Search for contacts.
        
        Args:
            query (str, optional): SGQL query string
            email (str, optional): Email address to search for
            
        Returns:
            Dict: Search results
        """
        data = {}
        if query:
            data["query"] = query
        elif email:
            data["query"] = f"email LIKE '{email}'"
        return self._make_request("POST", "/marketing/contacts/search", data)

    def get_lists(self) -> Dict:
        """Get all contact lists.
        
        Returns:
            Dict: List of contact lists
        """
        return self._make_request("GET", "/marketing/lists")

    def get_unsubscribe_groups(self) -> Dict:
        """Get all unsubscribe groups.
        
        Returns:
            Dict: List of unsubscribe groups
        """
        return self._make_request("GET", "/asm/groups") 