from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from datetime import datetime

LOGO_URL = "https://logo.clearbit.com/qonto.com"

@dataclass
class QontoIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Qonto integration.
    
    Attributes:
        organization_slug (str): Qonto organization identifier
        secret_key (str): Qonto API secret key
        base_url (str): Base URL for Qonto API. Defaults to "https://thirdparty.qonto.com/v2"
    """
    organization_slug: str
    secret_key: str
    base_url: str = "https://thirdparty.qonto.com/v2"

class QontoIntegration(Integration):
    """Qonto API integration client.
    
    This class provides methods to interact with Qonto's API endpoints
    for banking and financial operations.
    """

    __configuration: QontoIntegrationConfiguration

    def __init__(self, configuration: QontoIntegrationConfiguration):
        """Initialize Qonto client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"{self.__configuration.organization_slug}:{self.__configuration.secret_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None) -> Dict:
        """Make HTTP request to Qonto API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
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
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Qonto API request failed: {str(e)}")

    def get_organization(self) -> Dict:
        """Get organization details.
        
        Returns:
            Dict: Organization information
        """
        return self._make_request("/organization")

    def get_accounts(self) -> List[Dict]:
        """Get list of bank accounts.
        
        Returns:
            List[Dict]: List of accounts
        """
        response = self._make_request("/accounts")
        return response.get("accounts", [])

    def get_transactions(self, 
                        iban: str,
                        status: str = "completed",
                        start_date: Optional[str] = None,
                        end_date: Optional[str] = None) -> List[Dict]:
        """Get list of transactions for an account.
        
        Args:
            iban (str): Account IBAN
            status (str, optional): Transaction status. Defaults to "completed"
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            List[Dict]: List of transactions
        """
        params = {
            "iban": iban,
            "status": status
        }
        if start_date:
            params["settled_at_from"] = start_date
        if end_date:
            params["settled_at_to"] = end_date
            
        response = self._make_request("/transactions", params=params)
        return response.get("transactions", [])

    def get_attachments(self, transaction_id: str) -> List[Dict]:
        """Get attachments for a specific transaction.
        
        Args:
            transaction_id (str): Transaction ID
            
        Returns:
            List[Dict]: List of attachments
        """
        response = self._make_request(f"/transactions/{transaction_id}/attachments")
        return response.get("attachments", []) 