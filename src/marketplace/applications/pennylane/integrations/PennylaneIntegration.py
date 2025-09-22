from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, Optional
import requests
import json
from src.utils.Storage import save_json
import os
from abi.services.cache.CacheFactory import CacheFactory
from lib.abi.services.cache.CachePort import DataType
from datetime import timedelta

cache = CacheFactory.CacheFS_find_storage(subpath="pennylane")

@dataclass
class PennylaneIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Pennylane integration.
    
    Attributes:
        api_key (str): Pennylane API key for authentication
        base_url (str): Base URL for Pennylane API. Defaults to "https://app.pennylane.com/api/external/v1/"
    """
    api_key: str
    base_url: str = "https://app.pennylane.com/api/external"
    data_store_path: str = "datastore/pennylane"

class PennylaneIntegration(Integration):
    """Pennylane API integration client.
    
    This integration provides methods to interact with Pennylane's API endpoints
    for accounting and financial management.
    """

    __configuration: PennylaneIntegrationConfiguration

    def __init__(self, configuration: PennylaneIntegrationConfiguration):
        """Initialize Pennylane client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

    def _make_request(self, endpoint: str, method: str = "GET", json: Dict = {}, params: Dict = {}) -> Dict:
        """Make HTTP request to Pennylane API.
        
        Args:
            endpoint (str): API endpoint
            method (str): HTTP method (GET, POST, etc.). Defaults to "GET"
            json (Dict, optional): JSON body for requests. Defaults to {}.
            
        Returns:
            Dict: Response JSON
            
        Raises:
            IntegrationConnectionError: If request fails
        """
        url: str = f"{self.__configuration.base_url}/{endpoint}"
        
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                json=json,
                params=params
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Pennylane API request failed: {str(e)}")
        
    def _get_all_items(self, endpoint: str, params: Dict = {}) -> list:
        """Get all items from an endpoint.
        
        Args:
            endpoint (str): API endpoint
            params (Dict, optional): Parameters for the request. Defaults to {}.
        """
        data: list = []
        has_more = True
        
        while has_more:
            response = self._make_request(endpoint, params=params)
            has_more = response.get('has_more', False)
            items = response.get('items', [])
            if items:
                data.extend(items)
            if has_more:
                params['cursor'] = response.get('next_cursor')
        return data
        
    def list_customers(
        self,
        sort: str = "-id",
        filters: list = [],
    ) -> list:
        """Get list of customers.
        
        Args:
            sort (str, optional): Sort by field. Defaults to "-id".
            filters (list, optional): List of filter dictionaries to filter customers.
                Example: [{"field": "country_alpha2", "operator": "eq", "value": "FR"}]
            
        Returns:
            List[Dict]: List of customers
        """
        params: dict = {
            "limit": 100,
            "sort": sort
        }
        
        if filters:
            params["filter"] = json.dumps(filters)

        customers = self._get_all_items("v2/customers", params=params)
        filter_str = '_'.join([f"filter_[{json.dumps(f)}]" for f in filters]).replace(' ', '_')
        file_name = "list_customers.json"
        if filter_str:
            file_name = f"list_customers_{filter_str}.json"
        save_json(customers, os.path.join(self.__configuration.data_store_path, "list_customers"), file_name)
        return customers
    
    @cache(lambda self, customer_id: "get_customer_" + customer_id, cache_type=DataType.JSON, ttl=timedelta(days=1))
    def get_customer(self, customer_id: str) -> Dict:
        """Get details for a specific customer.
        
        Args:
            customer_id (str): ID of the customer to retrieve
            
        Returns:
            Dict: Customer details
        """
        prefix = os.path.join(self.__configuration.data_store_path, "get_customer", customer_id)
        file_name = f"{customer_id}.json"
        customer = self._make_request(f"v2/customers/{customer_id}")
        save_json(customer, prefix, file_name)
        return customer
        
    def list_customer_invoices(
        self,
        sort: str = "-date",
        filters: list = [],
        customer_id: Optional[str] = None,
        start_date: Optional[str] = None,
    ) -> list:
        """Get list customers of invoices.
        
        Args:
            sort (str, optional): Sort by field. Defaults to "-date". Other options -id
            filters (list, optional): List of filter dictionaries to filter invoices.
                Example: [{"field": "status", "operator": "scope", "value": "late_status"}]
            customer_id (str, optional): Customer ID to filter invoices by. Defaults to None.
            start_date (str, optional): Start date in format YYYY-MM-DD to filter invoices by. Defaults to None.
            
        Returns:
            List[Dict]: List of invoices
        """
        params: dict = {
            "limit": 100,
            "sort": sort
        }
        
        if customer_id:
            filters.append(
                { 
                    "field": 'customer_id', 
                    "operator": 'match', 
                    "value": customer_id,
                }
            )
        if start_date:
            filters.append(
                {
                    "field": 'date',
                    "operator": 'gteq',
                    "value": start_date,
                }
            )
            
        if filters:
            params["filter"] = json.dumps(filters)
            
        invoices = self._get_all_items("v2/customer_invoices", params=params)
        filter_str = '_'.join([f"filter_[{json.dumps(f)}]" for f in filters]).replace(' ', '_')
        file_name = "list_customer_invoices.json"
        if filter_str:
            file_name = f"list_customer_invoices_{filter_str}.json"
        save_json(invoices, os.path.join(self.__configuration.data_store_path, "list_customer_invoices"), file_name)
        return invoices
    
    @cache(lambda self, invoice_id: "get_customer_invoice_" + invoice_id, cache_type=DataType.JSON, ttl=timedelta(days=1))
    def get_customer_invoice(self, invoice_id: str) -> Dict:
        """Get a specific customer invoice.
        
        Args:
            invoice_id (str): Invoice ID to retrieve
            
        Returns:
            Dict: Invoice details
        """
        prefix = os.path.join(self.__configuration.data_store_path, "get_customer_invoice", invoice_id)
        file_name = f"{invoice_id}.json"
        invoice = self._make_request(f"v2/customer_invoices/{invoice_id}")
        save_json(invoice, prefix, file_name)
        return invoice
    
    @cache(lambda self, invoice_id: "get_customer_invoice_categories_" + invoice_id, cache_type=DataType.JSON, ttl=timedelta(days=1))
    def get_customer_invoice_categories(self, invoice_id: str) -> list:
        """Get categories for a specific customer invoice.
        """
        invoice_categories = self._get_all_items(f"v2/customer_invoices/{invoice_id}/categories")
        prefix = os.path.join(self.__configuration.data_store_path, "get_customer_invoice_categories", invoice_id)
        file_name = f"{invoice_id}.json"
        save_json(invoice_categories, prefix, file_name)
        return invoice_categories
    
    def list_categories(
        self,
        sort: str = "-id",
        filters: list = [],
    ) -> list:
        """Get list of categories.
        
        Args:
            sort (str, optional): Sort by field. Defaults to "-id".
            filters (list, optional): List of filter dictionaries to filter categories.
                Example: [{"field": "name", "operator": "eq", "value": "Sales"}]
            limit (int, optional): Maximum number of categories to return. Defaults to 100.
            
        Returns:
            List[Dict]: List of categories
        """
        params: dict = {
            "limit": 100,
            "sort": sort
        }
        
        if filters:
            params["filter"] = json.dumps(filters)
            
        categories = self._get_all_items("v2/categories", params=params)
        filter_str = '_'.join([f"filter_[{json.dumps(f)}]" for f in filters]).replace(' ', '_')
        file_name = "list_categories.json"
        if filter_str:
            file_name = f"list_categories_{filter_str}.json"
        save_json(categories, os.path.join(self.__configuration.data_store_path, "list_categories"), file_name)
        return categories
    
    def list_category_groups(self) -> list:
        """Get list of category groups.
        """
        params: dict = {
            "limit": 100,
        }
        category_groups = self._get_all_items("v2/category_groups", params=params)
        save_json(category_groups, os.path.join(self.__configuration.data_store_path, "list_category_groups"), "list_category_groups.json")
        return category_groups
    
    def list_bank_transactions(
        self,
        sort: str = "-id",
        filters: list = [],
    ) -> list:
        """Get list of bank transactions.
        
        Returns:
            List[Dict]: List of bank transactions
        """
        params: dict = {
            "limit": 100,
            "sort": sort
        }
        
        if filters:
            params["filter"] = json.dumps(filters)
            
        bank_transactions = self._get_all_items("v2/transactions", params=params)
        filter_str = '_'.join([f"filter_[{json.dumps(f)}]" for f in filters]).replace(' ', '_')
        file_name = "list_bank_transactions.json"
        if filter_str:
            file_name = f"list_bank_transactions_{filter_str}.json"
        save_json(bank_transactions, os.path.join(self.__configuration.data_store_path, "list_bank_transactions"), file_name)
        return bank_transactions
    
def as_tools(configuration: PennylaneIntegrationConfiguration):
    """Convert Pennylane integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = PennylaneIntegration(configuration)

    class ListCustomersSchema(BaseModel):
        pass

    class GetCustomerDetailsSchema(BaseModel):
        customer_id: str = Field(..., description="ID of the customer to retrieve")
    
    class ListCustomersInvoicesSchema(BaseModel):
        start_date: Optional[str] = Field(None, description="Start date in format YYYY-MM-DD to filter invoices by")
        customer_id: Optional[str] = Field(None, description="Customer ID to filter invoices by")

    class GetCustomerInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to retrieve")

    return [
        StructuredTool(
            name="pennylane_list_customers",
            description="List customers from Pennylane.",
            func=integration.list_customers,
            args_schema=ListCustomersSchema
        ),
        StructuredTool(
            name="pennylane_get_customer_details",
            description="Get details for a specific customer from Pennylane.",
            func=lambda customer_id: integration.get_customer(customer_id),
            args_schema=GetCustomerDetailsSchema
        ),
        StructuredTool(
            name="pennylane_list_customers_invoices",
            description="List customer invoices from Pennylane.",
            func=lambda start_date, customer_id: integration.list_customer_invoices(start_date, customer_id),
            args_schema=ListCustomersInvoicesSchema
        ),
        StructuredTool(
            name="pennylane_get_customer_invoice",
            description="Get a specific customer invoice from Pennylane.",
            func=lambda invoice_id: integration.get_customer_invoice(invoice_id),
            args_schema=GetCustomerInvoiceSchema
        ),
    ]