from lib.abi.integration.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests

LOGO_URL = "https://logo.clearbit.com/mercury.com"


@dataclass
class MercuryIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Mercury integration.

    Attributes:
        api_key (str): Mercury API key for authentication
        base_url (str): Base URL for Mercury API. Defaults to "https://api.mercury.com/api/v1"
    """

    api_key: str
    base_url: str = "https://api.mercury.com/api/v1"


class MercuryIntegration(Integration):
    """Mercury API integration client.

    This integration provides methods to interact with Mercury's API endpoints
    for banking and financial operations. More information at:
    https://docs.mercury.com/reference/welcome-to-mercury-api
    """

    __configuration: MercuryIntegrationConfiguration

    def __init__(self, configuration: MercuryIntegrationConfiguration):
        """Initialize Mercury client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json",
        }

    def _make_request(
        self, endpoint: str, method: str = "GET", params: Dict = None
    ) -> Dict:
        """Make HTTP request to Mercury API.

        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            params (Dict, optional): Query parameters. Defaults to None

        Returns:
            Dict: Response JSON

        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}{endpoint}"

        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Mercury API request failed: {str(e)}")

    def get_accounts(self) -> List[Dict]:
        """Retrieve information about all your bank accounts."""
        response = self._make_request("/accounts")
        return response.get("accounts", [])

    def get_account_details(self, account_id: str) -> Dict:
        """Get detailed information for a specific account.

        Args:
            account_id (str): Account ID
        """
        return self._make_request(f"/accounts/{account_id}")

    def get_account_cards(self, account_id: str) -> List[Dict]:
        """Retrieve information about cards associated with a specific account.

        Args:
            account_id (str): Account ID
        """
        return self._make_request(f"/accounts/{account_id}/cards")

    def get_transactions(
        self,
        account_id: str,
        limit: Optional[int] = 500,
        offset: Optional[int] = 0,
        status: Optional[str] = "sent",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        search: Optional[str] = None,
    ) -> List[Dict]:
        """Get list of transactions for an account.

        Args:
            account_id (str): Account ID
            limit (int, optional): Limit how many transactions to retrieve. Defaults to 500
            offset (int, optional): Number of most recent transactions to omit. Defaults to 0
            status (str, optional): Transaction status filter ("pending"|"sent"|"cancelled"|"failed"). Defaults to "sent"
            start_date (str, optional): Earliest createdAt date to filter (YYYY-MM-DD or ISO 8601). Defaults to 30 days ago
            end_date (str, optional): Latest createdAt date to filter (YYYY-MM-DD or ISO 8601). Defaults to current day
            search (str, optional): Search term to look for in transaction descriptions

        Returns:
            List[Dict]: List of transactions
        """
        params = {"limit": limit, "offset": offset, "status": status}
        if start_date:
            params["start"] = start_date
        if end_date:
            params["end"] = end_date
        if search:
            params["search"] = search

        response = self._make_request(
            f"/account/{account_id}/transactions", params=params
        )
        return response.get("transactions", [])

    def get_transaction_details(self, account_id: str, transaction_id: str) -> Dict:
        """Get detailed information for a specific transaction.

        Args:
            transaction_id (str): Transaction ID

        Returns:
            Dict: Transaction details
        """
        return self._make_request(
            f"/account/{account_id}/transactions/{transaction_id}"
        )

    def get_recipients(self) -> List[Dict]:
        """Retrieve information about all your recipients."""
        return self._make_request("/recipients")

    def get_recipient_details(self, recipient_id: str) -> Dict:
        """Get detailed information for a specific recipient.

        Args:
            recipient_id (str): Recipient ID
        """
        return self._make_request(f"/recipients/{recipient_id}")


def as_tools(configuration: MercuryIntegrationConfiguration):
    """Convert Notion integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = MercuryIntegration(configuration)

    class GetAccountsSchema(BaseModel):
        pass

    class GetAccountDetailsSchema(BaseModel):
        account_id: str = Field(..., description="Account ID")

    class GetAccountCardsSchema(BaseModel):
        account_id: str = Field(..., description="Account ID")

    class GetTransactionsSchema(BaseModel):
        account_id: str = Field(..., description="Account ID")
        limit: Optional[int] = Field(
            ..., description="Limit how many transactions to retrieve. Defaults to 500"
        )
        offset: Optional[int] = Field(
            ..., description="Number of most recent transactions to omit. Defaults to 0"
        )
        status: Optional[str] = Field(
            ...,
            description='Transaction status filter ("pending"|"sent"|"cancelled"|"failed"). Defaults to "sent"',
        )
        start_date: Optional[str] = Field(
            ..., description="Start date in YYYY-MM-DD format"
        )
        end_date: Optional[str] = Field(
            ..., description="End date in YYYY-MM-DD format"
        )
        search: Optional[str] = Field(
            ..., description="Search term to look for in transaction descriptions"
        )

    class GetTransactionDetailsSchema(BaseModel):
        account_id: str = Field(..., description="Account ID")
        transaction_id: str = Field(..., description="Transaction ID")

    class GetRecipientsSchema(BaseModel):
        pass

    class GetRecipientDetailsSchema(BaseModel):
        recipient_id: str = Field(..., description="Recipient ID")

    return [
        StructuredTool(
            name="mercury_get_accounts",
            description="Get list of bank accounts",
            func=lambda: integration.get_accounts(),
            args_schema=GetAccountsSchema,
        ),
        StructuredTool(
            name="mercury_get_account_details",
            description="Get detailed information for a specific account",
            func=lambda account_id: integration.get_account_details(account_id),
            args_schema=GetAccountDetailsSchema,
        ),
        StructuredTool(
            name="mercury_get_account_cards",
            description="Get list of cards associated with an account",
            func=lambda account_id: integration.get_account_cards(account_id),
            args_schema=GetAccountCardsSchema,
        ),
        StructuredTool(
            name="mercury_get_transactions",
            description="Get list of transactions for an account",
            func=lambda account_id,
            limit,
            offset,
            status,
            start_date,
            end_date,
            search: integration.get_transactions(
                account_id, limit, offset, status, start_date, end_date, search
            ),
            args_schema=GetTransactionsSchema,
        ),
        StructuredTool(
            name="mercury_get_transaction_details",
            description="Get detailed information for a specific transaction",
            func=lambda account_id, transaction_id: integration.get_transaction_details(
                account_id, transaction_id
            ),
            args_schema=GetTransactionDetailsSchema,
        ),
        StructuredTool(
            name="mercury_get_recipients",
            description="Get list of recipients",
            func=lambda: integration.get_recipients(),
            args_schema=GetRecipientsSchema,
        ),
        StructuredTool(
            name="mercury_get_recipient_details",
            description="Get detailed information for a specific recipient",
            func=lambda recipient_id: integration.get_recipient_details(recipient_id),
            args_schema=GetRecipientDetailsSchema,
        ),
    ]
