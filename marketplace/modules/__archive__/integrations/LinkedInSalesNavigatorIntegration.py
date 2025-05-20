from abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
import requests
from pydantic import BaseModel, Field
from typing import Optional, Dict

LOGO_URL = "https://play-lh.googleusercontent.com/zb0NgZjxTlO6vMpGyjVmgMPN-xRbo31Q5xGNbjM8wYhiaU7xFKlGGCYl2Ws4-Nl0iBE"


@dataclass
class LinkedInSalesNavigatorConfiguration(IntegrationConfiguration):
    """Configuration for LinkedIn Sales Navigator integration.

    Attributes:
        li_at (str): LinkedIn li_at cookie value for authentication
        JSESSIONID (str): LinkedIn JSESSIONID cookie value for authentication
        base_url (str): Base URL for LinkedIn Sales Navigator API
    """

    li_at: str
    JSESSIONID: str
    base_url: str = "https://www.linkedin.com/sales-api"


class LinkedInSalesNavigatorIntegration(Integration):
    """LinkedIn Sales Navigator API integration client.

    This integration provides methods to interact with LinkedIn Sales Navigator API endpoints
    for accessing accounts, leads, and messaging features.
    """

    __configuration: LinkedInSalesNavigatorConfiguration

    def __init__(self, configuration: LinkedInSalesNavigatorConfiguration):
        """Initialize LinkedIn Sales Navigator client with authentication cookies."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.cookies = {
            "li_at": self.__configuration.li_at,
            "JSESSIONID": f'"{self.__configuration.JSESSIONID}"',
        }

        self.headers = {
            "X-Li-Lang": "en_US",
            "Accept": "application/vnd.linkedin.normalized+json+2.1",
            "csrf-token": self.__configuration.JSESSIONID,
            "X-RestLi-Protocol-Version": "2.0.0",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _make_request(
        self, method: str, endpoint: str, params: dict = None, data: dict = None
    ) -> dict:
        """Make HTTP request to LinkedIn Sales Navigator API."""
        url = f"{self.__configuration.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                cookies=self.cookies,
                params=params,
                json=data,
            )
            response.raise_for_status()
            return response.json() if response.content else {}
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(
                f"LinkedIn Sales Navigator API request failed: {str(e)}"
            )

    def get_account(self, account_id: str) -> dict:
        """Get detailed information about a specific account.

        Args:
            account_id (str): LinkedIn Sales Navigator account ID

        Returns:
            dict: Account information including company details, employee count, etc.
        """
        endpoint = f"/accounts/{account_id}"
        return self._make_request("GET", endpoint)

    def search_accounts(
        self,
        keywords: str = None,
        filters: dict = None,
        start: int = 0,
        count: int = 25,
    ) -> Dict:
        """Search for accounts using various filters.

        Args:
            keywords (str, optional): Search keywords
            filters (dict, optional): Dictionary of filter parameters
            start (int): Starting position for pagination
            count (int): Number of results per page

        Returns:
            Dict: JSON containing account search results
        """
        endpoint = "/search/accounts"
        params = {"q": "search", "start": start, "count": count}

        if keywords:
            params["keywords"] = keywords

        if filters:
            params.update(filters)

        response = self._make_request("GET", endpoint, params=params)
        return response

    def get_lead(self, lead_id: str) -> dict:
        """Get detailed information about a specific lead.

        Args:
            lead_id (str): LinkedIn Sales Navigator lead ID

        Returns:
            dict: Lead information including profile details, current role, etc.
        """
        endpoint = f"/leads/{lead_id}"
        return self._make_request("GET", endpoint)

    def search_leads(
        self,
        keywords: str = None,
        filters: dict = None,
        start: int = 0,
        count: int = 25,
    ) -> Dict:
        """Search for leads using various filters.

        Args:
            keywords (str, optional): Search keywords
            filters (dict, optional): Dictionary of filter parameters
            start (int): Starting position for pagination
            count (int): Number of results per page

        Returns:
            Dict: JSON containing lead search results
        """
        endpoint = "/search/leads"
        params = {"q": "search", "start": start, "count": count}

        if keywords:
            params["keywords"] = keywords

        if filters:
            params.update(filters)

        response = self._make_request("GET", endpoint, params=params)
        return response

    def send_message(self, recipient_id: str, message: str) -> dict:
        """Send a message to a lead.

        Args:
            recipient_id (str): LinkedIn member ID of the recipient
            message (str): Message content to send

        Returns:
            dict: Response containing message status and details
        """
        endpoint = "/messages"
        data = {"recipients": [recipient_id], "body": message}
        return self._make_request("POST", endpoint, data=data)

    def get_conversation_history(self, conversation_id: str, count: int = 50) -> Dict:
        """Get message history for a specific conversation.

        Args:
            conversation_id (str): LinkedIn conversation ID
            count (int): Number of messages to retrieve

        Returns:
            Dict: JSON containing message history
        """
        endpoint = f"/conversations/{conversation_id}/messages"
        params = {"count": count}

        response = self._make_request("GET", endpoint, params=params)
        return response


def as_tools(configuration: LinkedInSalesNavigatorConfiguration):
    """Convert LinkedIn Sales Navigator integration into LangChain tools."""
    from langchain_core.tools import StructuredTool

    integration = LinkedInSalesNavigatorIntegration(configuration)

    class GetAccountSchema(BaseModel):
        account_id: str = Field(..., description="LinkedIn Sales Navigator account ID")

    class SearchAccountsSchema(BaseModel):
        keywords: Optional[str] = Field(None, description="Search keywords")
        filters: Optional[Dict] = Field(
            None, description="Dictionary of filter parameters"
        )
        start: int = Field(default=0, description="Starting position for pagination")
        count: int = Field(default=25, description="Number of results per page")

    class GetLeadSchema(BaseModel):
        lead_id: str = Field(..., description="LinkedIn Sales Navigator lead ID")

    class SearchLeadsSchema(BaseModel):
        keywords: Optional[str] = Field(None, description="Search keywords")
        filters: Optional[Dict] = Field(
            None, description="Dictionary of filter parameters"
        )
        start: int = Field(default=0, description="Starting position for pagination")
        count: int = Field(default=25, description="Number of results per page")

    class SendMessageSchema(BaseModel):
        recipient_id: str = Field(
            ..., description="LinkedIn member ID of the recipient"
        )
        message: str = Field(..., description="Message content to send")

    class GetConversationHistorySchema(BaseModel):
        conversation_id: str = Field(..., description="LinkedIn conversation ID")
        count: int = Field(default=50, description="Number of messages to retrieve")

    return [
        StructuredTool(
            name="linkedinsalesnavigator_get_account",
            description="Get detailed information about a specific Sales Navigator account",
            func=lambda account_id: integration.get_account(account_id),
            args_schema=GetAccountSchema,
        ),
        StructuredTool(
            name="linkedinsalesnavigator_search_accounts",
            description="Search for accounts using various filters in Sales Navigator",
            func=lambda keywords=None,
            filters=None,
            start=0,
            count=25: integration.search_accounts(keywords, filters, start, count),
            args_schema=SearchAccountsSchema,
        ),
        StructuredTool(
            name="linkedinsalesnavigator_get_lead",
            description="Get detailed information about a specific Sales Navigator lead",
            func=lambda lead_id: integration.get_lead(lead_id),
            args_schema=GetLeadSchema,
        ),
        StructuredTool(
            name="linkedinsalesnavigator_search_leads",
            description="Search for leads using various filters in Sales Navigator",
            func=lambda keywords=None,
            filters=None,
            start=0,
            count=25: integration.search_leads(keywords, filters, start, count),
            args_schema=SearchLeadsSchema,
        ),
        StructuredTool(
            name="linkedinsalesnavigator_send_message",
            description="Send a message to a lead in Sales Navigator",
            func=lambda recipient_id, message: integration.send_message(
                recipient_id, message
            ),
            args_schema=SendMessageSchema,
        ),
        StructuredTool(
            name="linkedinsalesnavigator_get_conversation_history",
            description="Get message history for a specific conversation in Sales Navigator",
            func=lambda conversation_id, count=50: integration.get_conversation_history(
                conversation_id, count
            ),
            args_schema=GetConversationHistorySchema,
        ),
    ]
