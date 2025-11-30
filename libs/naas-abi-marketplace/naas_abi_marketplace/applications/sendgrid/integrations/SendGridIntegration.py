import time
from dataclasses import dataclass
from typing import Dict, List, Optional

import requests
from naas_abi_core.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)


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
        self.__configuration = configuration
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json",
        }

    def _make_request(self, method: str, endpoint: str, json: Dict = {}) -> Dict:
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
                method=method, url=url, headers=self.headers, json=json
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"SendGrid API request failed: {str(e)}")

    def create_contacts(
        self, contacts: List[Dict], list_ids: List[str], wait: bool = True
    ) -> Dict:
        """Create or update contacts and add them to specified lists.

        Args:
            contacts (List[Dict]): List of contact data dictionaries
            list_ids (List[str]): List of list IDs to add contacts to
            wait (bool, optional): Wait for job completion. Defaults to True.

        Returns:
            Dict: Job status response
        """
        data = {"list_ids": list_ids, "contacts": contacts}
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

    def search_contacts(
        self, query: Optional[str] = None, email: Optional[str] = None
    ) -> Dict:
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

    def send_email(
        self,
        from_email: str,
        to_emails: List[str],
        subject: str,
        html_content: str,
        plain_text_content: Optional[str] = None,
    ) -> Dict:
        """Send an email using SendGrid.

        Args:
            from_email (str): Sender email address
            to_emails (List[str]): List of recipient email addresses
            subject (str): Email subject line
            html_content (str): HTML content of the email
            plain_text_content (Optional[str]): Plain text version of the email

        Returns:
            Dict: API response
        """
        data = {
            "personalizations": [{"to": [{"email": email} for email in to_emails]}],
            "from": {"email": from_email},
            "subject": subject,
            "content": [{"type": "text/html", "value": html_content}],
        }

        if plain_text_content:
            data["content"] = [{"type": "text/plain", "value": plain_text_content}]

        return self._make_request("POST", "/mail/send", data)


def as_tools(configuration: SendGridIntegrationConfiguration):
    """Convert SendGrid integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = SendGridIntegration(configuration)

    class CreateContactsSchema(BaseModel):
        contacts: List[Dict] = Field(
            ..., description="List of contact data dictionaries"
        )
        list_ids: List[str] = Field(
            ..., description="List of list IDs to add contacts to"
        )

    class SearchContactsSchema(BaseModel):
        query: Optional[str] = Field(None, description="SGQL query string")
        email: Optional[str] = Field(None, description="Email address to search for")

    class GetListsSchema(BaseModel):
        pass

    class GetUnsubscribeGroupsSchema(BaseModel):
        pass

    class SendEmailSchema(BaseModel):
        from_email: str = Field(..., description="Sender email address")
        to_emails: List[str] = Field(
            ..., description="List of recipient email addresses"
        )
        subject: str = Field(..., description="Email subject line")
        html_content: str = Field(..., description="HTML content of the email")
        plain_text_content: Optional[str] = Field(
            None, description="Plain text version of the email"
        )

    return [
        StructuredTool(
            name="sendgrid_create_contacts",
            description="Create or update contacts and add them to specified lists.",
            func=lambda contacts, list_ids: integration.create_contacts(
                contacts, list_ids
            ),
            args_schema=CreateContactsSchema,
        ),
        StructuredTool(
            name="sendgrid_search_contacts",
            description="Search for contacts.",
            func=lambda query, email: integration.search_contacts(query, email),
            args_schema=SearchContactsSchema,
        ),
        StructuredTool(
            name="sendgrid_get_lists",
            description="Get all contact lists.",
            func=lambda: integration.get_lists(),
            args_schema=GetListsSchema,
        ),
        StructuredTool(
            name="sendgrid_get_unsubscribe_groups",
            description="Get all unsubscribe groups.",
            func=lambda: integration.get_unsubscribe_groups(),
            args_schema=GetUnsubscribeGroupsSchema,
        ),
        StructuredTool(
            name="sendgrid_send_email",
            description="Send an email using SendGrid.",
            func=lambda **kwargs: integration.send_email(**kwargs),
            args_schema=SendEmailSchema,
        ),
    ]
