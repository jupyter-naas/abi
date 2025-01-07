from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta
from abi import logger

LOGO_URL = "https://logo.clearbit.com/agicap.com"

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
    __token: Optional[str] = None

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
        """Get list of accessible companies.
        
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

    def _get_date_range(self, date_start: Optional[str] = None, date_end: Optional[str] = None) -> tuple[str, str]:
        """Get formatted date range timestamps.
        
        Args:
            date_start (Optional[str]): Start date in YYYY-MM-DD format
            date_end (Optional[str]): End date in YYYY-MM-DD format
            
        Returns:
            tuple[str, str]: Tuple of start and end timestamps in milliseconds
        """
        first_day_month = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        last_day_month = first_day_month + relativedelta(months=1) - relativedelta(seconds=1)
        
        if not date_start:
            date_start = first_day_month
        else:
            date_start = datetime.strptime(date_start, "%Y-%m-%d")
            
        if not date_end:
            date_end = last_day_month
        else:
            date_end = datetime.strptime(date_end, "%Y-%m-%d")
            
        ts_start = date_start.strftime("%s") + "000"
        ts_end = date_end.strftime("%s") + "000"
        return ts_start, ts_end

    def _get_excel_banque(
        self, 
        company_id: str, 
        banque_id: str, 
        date_start: str = None,
        date_end: str = None, 
        budget: bool = False, 
        actual: bool = False,
        forecast_raw_data: bool = False, 
        daily: bool = False
    ) -> requests.Response:
        """Export Excel Bank Report from Agicap.

        Args:
            company_id (str): Company identifier
            banque_id (str): Bank account identifier
            date_start (str): Start date in YYYY-MM-DD format
            date_end (str): End date in YYYY-MM-DD format
            budget (bool): Include budget data
            actual (bool): Include actual data
            forecast_raw_data (bool): Include forecast raw data
            daily (bool): Use daily view
            
        Returns:
            requests.Response: Response object
        """
        url = "https://app.agicap.com/api/exportexcel/ExportExcelBanque"
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Accept-Language": "fr",
            "Authorization": f"Bearer {self.__configuration.bearer_token}",
            "EntrepriseId": company_id,
            "Content-Type": "application/json"
        }
        date_start, date_end = self._get_date_range(date_start, date_end)
        payload = {
            "Scenario": {
                "CouleurR": 0,
                "CouleurG": 0,
                "CouleurB": 0,
                "isSelected": True,
                "isEdit": False,
                "Id": 0,
            },
            "DateBegin": date_start,
            "DateEnd": date_end,
            "BanquesId": [str(banque_id)],
            "Periodicite": {"Day": 0, "Month": 1}
        }

        if actual:
            payload["Scenario"]["tableauDeBordPrevisionel"] = True
        if budget:
            payload["Scenario"]["objectifs"] = True
        if forecast_raw_data:
            payload["Scenario"]["forecastRawData"] = True
        if daily:
            payload["Scenario"]["visionJournaliere"] = True
        return requests.post(url, headers=headers, json=payload)
    
    def export_actual(self, company_id: str, account_id: str, date_start: str, date_end: str) -> list[dict]:
        """Export actual bank transactions from Agicap.
        
        Retrieves actual bank transactions for the specified account and date range,
        processes the Excel report and returns the data as a list of dictionaries.
        
        Args:
            company_id (str): Company identifier
            account_id (str): Account identifier 
            date_start (str): Start date in YYYY-MM-DD format
            date_end (str): End date in YYYY-MM-DD format
            
        Returns:
            list[dict]: List of transactions as dictionaries
        """
        response = self._get_excel_banque(
            company_id,
            account_id,
            date_start=date_start,
            date_end=date_end,
            actual=True
        )
        
        if not response:
            return []
            
        df = pd.read_excel(response.content, header=2)
        
        # Clean up dataframe
        df = (df
              .drop([col for col in df.columns if col.startswith("Unnamed")], axis=1)
              .dropna())
        
        # Add company_id and account_id to each row
        df["company_id"] = company_id           
        df["account_id"] = account_id
        
        # Convert to dictionary
        return df.to_dict(orient="records")
    
    def export_budget(self, company_id: str, account_id: str, date_start: str, date_end: str) -> list[dict]:
        """Export budget vs actual comparison from Agicap.
        
        Retrieves budget vs actual comparison data for the specified account and date range,
        processes the Excel report and returns the data as a list of dictionaries.
        
        Args:
            company_id (str): Company identifier
            account_id (str): Account identifier 
            date_start (str): Start date in YYYY-MM-DD format
            date_end (str): End date in YYYY-MM-DD format
            
        Returns:
            list[dict]: List of budget comparison records as dictionaries
        """
        response = self._get_excel_banque(
            company_id,
            account_id, 
            date_start=date_start,
            date_end=date_end,
            budget=True
        )
        
        if not response:
            return []
            
        df = self._process_budget_excel(response.content, company_id, account_id)
        return df.to_dict(orient="records")

    def _process_budget_excel(self, content: bytes, company_id: str, account_id: str) -> pd.DataFrame:
        """Process budget Excel report from Agicap.
        
        Args:
            content (bytes): Excel file content
            company_id (str): Company identifier
            account_id (str): Account identifier
            
        Returns:
            pd.DataFrame: Processed DataFrame with budget comparison data
        """
        df = pd.read_excel(content, header=2)
        
        # Clean up dataframe
        df = (df
              .iloc[1:]  # Skip first row
              .reset_index(drop=True)
              .drop(["Unnamed: 1"], axis=1, errors='ignore'))

        # Process columns
        df = self._process_budget_columns(df)
        
        # Add identifiers
        df["company_id"] = company_id
        df["account_id"] = account_id
        
        return df.dropna()

    def _process_budget_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        """Process budget DataFrame columns.
        
        Args:
            df (pd.DataFrame): Input DataFrame
            
        Returns:
            pd.DataFrame: DataFrame with processed columns
        """
        col_max_int = 1 + 12 * 5 * 2
        
        for i, col in enumerate(df.columns[1:]):
            if i >= col_max_int:
                df = df.drop(col, axis=1)
            elif col.startswith("Unnamed"):
                df[col] = (df[col]
                          .fillna("0")
                          .astype(str)
                          .str.replace('Non déf.', "0", regex=True))
                
                new_name = f"{df.columns[i]} - Prévisionnel"
                df = df.rename(columns={col: new_name})
                df[new_name] = df[new_name].fillna("0").astype(float)
                
        return df

    def get_transactions(
        self,
        company_id: str,
        account_id: str,
        limit: int = 100,
    ) -> Dict:
        """Get all transactions for a specific account.
        
        Args:
            company_id (str): Company identifier
            account_id (str): Account identifier
            limit (int): Number of transactions to retrieve

        Returns:
            pd.DataFrame: DataFrame containing all transactions
        """
        data = []
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
            "pagination": {"skip": skip, "take": 100}
        }
        while True:
            logger.info(f"Fetching transactions for account {account_id} with skip {skip} and take {100}")
            res = requests.post(url, headers=headers, json=payload)
            res.raise_for_status()
            if res.status_code == 200:
                result = res.json().get("Result", [])
            else:
                logger.error(f"Failed to fetch transactions for account {account_id} with skip {skip} and take {100}")
                break
                    
            # Parse and flatten results
            for r in result:
                data.append(self._flatten_dict(r))
                
            if len(result) == 0 or len(data) >= limit:
                break
                
            skip += 100

        df = pd.DataFrame(data).reset_index(drop=True)
        
        if len(df) > 0:
            i = 0
            df.columns = df.columns.str.upper()
            
            # Enrich with company info
            df.insert(loc=i, column="ENTREPRISE_ID", value=company_id)
            i += 1
            
            # Enrich with account info
            df.insert(loc=i, column="COMPTE_ID", value=account_id)

        return df.to_dict(orient="records")

    def _flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '_') -> Dict:
        """Flatten a nested dictionary.
        
        Args:
            d (Dict): Dictionary to flatten
            parent_key (str): Parent key for nested items
            sep (str): Separator for nested keys
            
        Returns:
            Dict: Flattened dictionary
        """
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self._flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, v))
        return dict(items)
    
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

    class ExportActualSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: str = Field(..., description="The ID of the account")
        date_start: str = Field(..., description="The start date in YYYY-MM-DD format")
        date_end: str = Field(..., description="The end date in YYYY-MM-DD format")

    class ExportBudgetSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: str = Field(..., description="The ID of the account")
        date_start: str = Field(..., description="The start date in YYYY-MM-DD format")
        date_end: str = Field(..., description="The end date in YYYY-MM-DD format")

    class GetTransactionsSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")
        account_id: str = Field(..., description="The ID of the account")
        limit: Optional[int] = Field(default=100, description="The number of transactions to retrieve")

    class GetDebtsSchema(BaseModel):
        company_id: str = Field(..., description="The ID of the company")

    return [
        StructuredTool(
            name="list_companies",
            description="List all companies",
            func=lambda: integration.list_companies(),
            args_schema=ListCompaniesSchema
        ),
        StructuredTool(
            name="get_company_accounts",
            description="Get all accounts for a company",
            func=lambda company_id: integration.get_company_accounts(company_id),
            args_schema=GetCompanyAccountsSchema
        ),
        StructuredTool(
            name="export_actual",
            description="Export actual bank transactions from Agicap",
            func=lambda company_id, account_id, date_start, date_end: integration.export_actual(company_id, account_id, date_start, date_end),
            args_schema=ExportActualSchema
        ),
        StructuredTool(
            name="export_budget",
            description="Export budget vs actual comparison from Agicap",
            func=lambda company_id, account_id, date_start, date_end: integration.export_budget(company_id, account_id, date_start, date_end),
            args_schema=ExportBudgetSchema
        ),
        StructuredTool(
            name="get_transactions",
            description="Get all transactions for a specific account",
            func=lambda company_id, account_id, limit: integration.get_transactions(company_id, account_id, limit),
            args_schema=GetTransactionsSchema
        ),
        StructuredTool(
            name="get_debts",
            description="Get company debts information",
            func=lambda company_id: integration.get_debts(company_id),
            args_schema=GetDebtsSchema
        ),
    ]
