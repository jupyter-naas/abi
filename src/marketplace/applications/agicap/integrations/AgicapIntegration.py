from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional, Annotated
import requests
from abi import logger


@dataclass
class AgicapIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Agicap integration.
    
    Attributes:
        username (str): Agicap username for authentication
        password (str): Agicap password for authentication
        api_token (str): API token for authentication
        bearer_token (str): Bearer token for authentication
        client_id (str): Client ID for OAuth authentication
        client_secret (str): Client secret for OAuth authentication
        base_url (str): Base URL for Agicap API
    """
    username: str
    password: str
    api_token: str
    bearer_token: str
    client_id: str
    client_secret: str
    base_url: str = "https://app.agicap.com/api"

class AgicapIntegration(Integration):
    """Agicap API integration client.
    
    This class provides methods to interact with Agicap's API endpoints
    for cash flow management and financial data.
    """

    __configuration: AgicapIntegrationConfiguration

    def __init__(self, configuration: AgicapIntegrationConfiguration):
        """Initialize Agicap client with credentials."""
        super().__init__(configuration)
        self.__configuration = configuration
        if not self.__configuration.bearer_token:
            self.__configuration.bearer_token = self._get_bearer_token()

    def _get_bearer_token(self) -> str:
        """Get authentication token from Agicap.
        
        Returns:
            str: Authentication token
        """
        url = f"{self.__configuration.base_url}/public/auth/v1/token"
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "password",
            "client_id": "legacy-token",
            "client_secret": self.__configuration.client_secret,
            "scope": "agicap:app",
            "username": self.__configuration.username,
            "password": self.__configuration.password
        }
        
        response = requests.post(url, headers=headers, data=data)
        response.raise_for_status()
        return response.json().get('access_token')
        
    def list_companies(self) -> Dict:
        """Get list of accessible companies from public API.
        
        Returns:
            Dict: List of companies with their details
        """        
        url = "https://openapi.agicap.com/api/companies"
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.__configuration.api_token}",
        }
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            return res.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Agicap API request failed: {str(e)}")
        
    def get_company_accounts(self, company_id: str) -> Dict:
        """Get all accounts for a company.
        
        Args:
            company_id (str): Company identifier
            
        Returns:
            Dict: List of accounts with their details
        """
        url = "https://app.agicap.com/api/banque/GetAll"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Authorization": f"Bearer {self.__configuration.bearer_token}",
            "Entrepriseid": company_id
        }
        try:
            res = requests.get(url, headers=headers)
            res.raise_for_status()
            return res.json().get("Result")
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Agicap API request failed: {str(e)}")
        
    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten a nested dictionary.
        
        Args:
            d (Dict): Dictionary to flatten
            parent_key (str): Parent key for nested items
            sep (str): Separator for nested keys
            
        Returns:
            Dict: Flattened dictionary
        """
        items: list = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
    def get_transactions(
        self,
        company_id: str,
        account_id: str,
        limit: int = 100,
    ) -> List[Dict]:
        """Get all transactions for a specific account.
        
        Args:
            company_id (str): Company identifier
            account_id (str): Account identifier
            limit (int): Number of transactions to retrieve

        Returns:
            List[Dict]: List of transactions
        """
        data = []
        take = 100
        if limit < take:
            take = limit
        skip = 0
        url = f"{self.__configuration.base_url}/paidtransaction/GetByFilters"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr",
            "Authorization": f"Bearer {self.__configuration.bearer_token}",
            "EntrepriseId": company_id,
            "Content-Type": "application/json"
        }
        payload = {
            "filters": {
                "nature": 1,
                "statusesToInclude": 0,
                "statusesToExclude": 0,
                "transactionWithProjectsDistributionStale": False,
                "includeTransactionWithoutProject": False,
                "transactionsType": 0,
                "categorizationState": 0,
                "bankAccountIds": [str(account_id)]
            },
            "sort": {"asc": False, "sortField": "0"},
            "pagination": {"skip": skip, "take": take}
        }
        while True:
            logger.info(f"Fetching transactions for account {account_id} with skip {skip} and take {take}")
            res = requests.post(url, headers=headers, json=payload)
            res.raise_for_status()
            if res.status_code == 200:
                result = res.json().get("Result", [])
            else:
                logger.error(f"Failed to fetch transactions for account {account_id} with skip {skip} and take {take}")
                break
                    
            # Parse and flatten results
            for r in result:
                data.append(self._flatten_dict(r))
                
            if len(result) == 0 or len(data) >= limit:
                break
                
            skip += 100
        return data

    def get_balance(self, company_id: str, account_id: Optional[str] = None) -> Dict:
        """Get account balance information.
        
        Args:
            company_id (str): Company identifier
            account_id (str): Account identifier
        """
        if account_id:
            url = f"https://app.agicap.com/api/forecasting/v2/bank/{account_id}/cash-balances?frequency=2"
        else:
            url = "https://app.agicap.com/api/forecasting/v2/bank/cash-balances?frequency=2&"
        headers = {
            "Accept": "application/json, text/plain, */*", 
            "Accept-Language": "fr",
            "Authorization": f"Bearer {self.__configuration.bearer_token}",
            "Content-Type": "application/json",
            "EntrepriseId": company_id
        }
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
    
    def get_debts(self, company_id: str) -> Dict:
        """Get company debts information.
        
        Args:
            company_id (str): Company identifier
            
        Returns:
            Dict: Debt information
        """
        url = f"https://debt-management.agicap.com/v3/entities/{company_id}/debts"
        headers = {
            "Accept": "application/json, text/plain, */*", 
            "Accept-Language": "fr",
            "Authorization": f"Bearer {self.__configuration.bearer_token}",
            "Content-Type": "application/json"
        }
        
        res = requests.get(url, headers=headers)
        res.raise_for_status()
        return res.json()
    
def as_tools(configuration: AgicapIntegrationConfiguration):
    """Convert Agicap integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = AgicapIntegration(configuration)

    class ListCompaniesSchema(BaseModel):
        pass

    class GetCompanyAccountsSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")

    class GetTransactionsSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: str = Field(..., description="The ID of the account")
        limit: Optional[Annotated[int, Field(
            description="The number of transactions to retrieve"
        )]] = 10

    class GetBalanceSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: Optional[str] = Field(description="The ID of the account")

    class GetDebtsSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")

    return [
        StructuredTool.from_function(
            name="agicap_list_companies",
            description="Get list of accessible companies with their ID from Agicap.",
            func=lambda: integration.list_companies(),
            args_schema=ListCompaniesSchema 
        ),
        StructuredTool.from_function(
            name="agicap_get_company_accounts",
            description="Get all accounts with their ID for a company in Agicap.",
            func=lambda company_id: integration.get_company_accounts(company_id),
            args_schema=GetCompanyAccountsSchema
        ),
        StructuredTool.from_function(
            name="agicap_get_transactions",
            description="Get all transactions for a specific account in Agicap.",
            func=lambda company_id, account_id, limit: integration.get_transactions(company_id, account_id, limit),
            args_schema=GetTransactionsSchema
        ),
        StructuredTool.from_function(
            name="agicap_get_balance",
            description="Get account balance information from Agicap. If account ID is not provided, a consolidated balance will be returned.",
            func=lambda company_id, account_id: integration.get_balance(company_id, account_id),
            args_schema=GetBalanceSchema
        ),
        StructuredTool.from_function(
            name="agicap_get_debts",
            description="Get company debts information from Agicap.",
            func=lambda company_id: integration.get_debts(company_id),
            args_schema=GetDebtsSchema
        )
    ]