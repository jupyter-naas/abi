from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from datetime import datetime

@dataclass
class PennylaneIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Pennylane integration.
    
    Attributes:
        api_key (str): Pennylane API key for authentication
        organization_id (str): Pennylane organization ID
        base_url (str): Base URL for Pennylane API. Defaults to "https://api.pennylane.tech"
    """
    api_key: str
    organization_id: str
    base_url: str = "https://api.pennylane.tech"

class PennylaneIntegration(Integration):
    """Pennylane API integration client.
    
    This class provides methods to interact with Pennylane's API endpoints
    for accounting and financial management.
    """

    __configuration: PennylaneIntegrationConfiguration

    def __init__(self, configuration: PennylaneIntegrationConfiguration):
        """Initialize Pennylane client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", json: Dict = None) -> Dict:
        """Make HTTP request to Pennylane API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            json (Dict, optional): JSON body for requests. Defaults to None.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url = f"{self.__configuration.base_url}/organizations/{self.__configuration.organization_id}{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Pennylane API request failed: {str(e)}")

    def get_invoices(self, 
                    start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> List[Dict]:
        """Get list of invoices.
        
        Args:
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            List[Dict]: List of invoices
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        return self._make_request("/invoices", json=params)

    def get_invoice_details(self, invoice_id: str) -> Dict:
        """Get detailed information about a specific invoice.
        
        Args:
            invoice_id (str): Invoice ID
            
        Returns:
            Dict: Invoice details
        """
        return self._make_request(f"/invoices/{invoice_id}")

    def get_customers(self) -> List[Dict]:
        """Get list of customers.
        
        Returns:
            List[Dict]: List of customers
        """
        return self._make_request("/customers")

    def get_customer_details(self, customer_id: str) -> Dict:
        """Get detailed information about a specific customer.
        
        Args:
            customer_id (str): Customer ID
            
        Returns:
            Dict: Customer details
        """
        return self._make_request(f"/customers/{customer_id}")

    def get_expenses(self, 
                    start_date: Optional[str] = None, 
                    end_date: Optional[str] = None) -> List[Dict]:
        """Get list of expenses.
        
        Args:
            start_date (str, optional): Start date in YYYY-MM-DD format
            end_date (str, optional): End date in YYYY-MM-DD format
            
        Returns:
            List[Dict]: List of expenses
        """
        params = {}
        if start_date:
            params["start_date"] = start_date
        if end_date:
            params["end_date"] = end_date
            
        return self._make_request("/expenses", json=params)

def as_tools(configuration: PennylaneIntegrationConfiguration):
    """Convert Pennylane integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = PennylaneIntegration(configuration)
    
    class DateRangeSchema(BaseModel):
        start_date: Optional[str] = Field(None, description="Start date in YYYY-MM-DD format")
        end_date: Optional[str] = Field(None, description="End date in YYYY-MM-DD format")

    class InvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="Invoice ID")

    class CustomerSchema(BaseModel):
        customer_id: str = Field(..., description="Customer ID")
    
    return [
        StructuredTool(
            name="get_pennylane_invoices",
            description="Get list of invoices with optional date range",
            func=lambda start_date, end_date: integration.get_invoices(start_date, end_date),
            args_schema=DateRangeSchema
        ),
        StructuredTool(
            name="get_pennylane_invoice_details",
            description="Get detailed information about a specific invoice",
            func=lambda invoice_id: integration.get_invoice_details(invoice_id),
            args_schema=InvoiceSchema
        ),
        StructuredTool(
            name="get_pennylane_customers",
            description="Get list of customers",
            func=lambda: integration.get_customers(),
            args_schema=BaseModel
        ),
        StructuredTool(
            name="get_pennylane_customer_details",
            description="Get detailed information about a specific customer",
            func=lambda customer_id: integration.get_customer_details(customer_id),
            args_schema=CustomerSchema
        ),
        StructuredTool(
            name="get_pennylane_expenses",
            description="Get list of expenses with optional date range",
            func=lambda start_date, end_date: integration.get_expenses(start_date, end_date),
            args_schema=DateRangeSchema
        )
    ] 