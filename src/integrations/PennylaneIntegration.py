from lib.abi.integration.integration import Integration, IntegrationConfiguration, IntegrationConnectionError
from dataclasses import dataclass
from typing import Dict, List, Optional
import requests
from datetime import datetime
from abi import logger

LOGO_URL = "https://app.pennylane.com/api/external/"

@dataclass
class PennylaneIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Pennylane integration.
    
    Attributes:
        api_key (str): Pennylane API key for authentication
        base_url (str): Base URL for Pennylane API. Defaults to "https://app.pennylane.com/api/external/v1/"
    """
    api_key: str
    base_url: str = "https://app.pennylane.com/api/external/v1"

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

    def _make_request(self, endpoint: str, method: str = "GET", json: Dict = None, params: Dict = {}) -> Dict:
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
        url = f"{self.__configuration.base_url}/{endpoint}"
        
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
        
    def list_customer_invoices(
            self,
            limit: int = -1,
            filter: Optional[str] = None
        ) -> List[Dict]:
        """Get list customers of invoices.
        
        Args:
            limit (int, optional): Number of invoices to return. Defaults to -1 (all).
            filter (str, optional): Filter string in JSON format to filter invoices.
                Example: '[{"field": "status", "operator": "scope", "value": "late_status"}]'
            
        Returns:
            List[Dict]: List of invoices
        """
        params = {
            "page": 1,
            "per_page": 20
        }
        if filter:
            params["filter"] = filter
            
        all_invoices = []
        while True:
            if limit != -1 and len(all_invoices) >= limit:
                break
                
            items = self._make_request("/customer_invoices", params=params)
            logger.info(f"Pennylane invoices: {items}")
            all_invoices.extend(items["invoices"])
            
            total_pages = items["total_pages"]
            if total_pages > params["current_page"]:
                params["page"] += 1
            else:
                break
                
        return all_invoices
    
    def get_customer_invoice(self, invoice_id: str) -> Dict:
        """Get a specific customer invoice.
        
        Args:
            invoice_id (str): Invoice ID to retrieve
            
        Returns:
            Dict: Invoice details
        """
        return self._make_request(f"/customer_invoices/{invoice_id}")
    
    def update_customer_invoice(self, invoice_id: str, transaction_reference: Optional[str] = None, categories: Optional[List[str]] = None) -> Dict:
        """Update a customer invoice's transaction reference and categories.
        
        Args:
            invoice_id (str): ID of the invoice to update
            transaction_reference (str, optional): New transaction reference
            categories (List[str], optional): List of category IDs to link to the invoice
            
        Returns:
            Dict: Updated invoice details
        """
        data = {}
        if transaction_reference is not None:
            data["transaction_reference"] = transaction_reference
        if categories is not None:
            data["categories"] = categories
            
        return self._make_request(f"/customer_invoices/{invoice_id}", method="PUT", json=data)
    
    def list_estimates(
        self,
        limit: int = -1,
        filter: Optional[str] = None
    ) -> List[Dict]:
        """Get list of customer estimates.
        
        Args:
            limit (int, optional): Number of estimates to return. Defaults to -1 (all).
            filter (str, optional): Filter string in JSON format to filter estimates.
                Example: '[{"field": "status", "operator": "scope", "value": "estimate_pending_status"}]'
                Available statuses:
                - estimate_pending_status: an estimate waiting to be denied or accepted
                - estimate_accepted_status: an estimate that has been accepted
                - estimate_denied_status: an estimate that has been denied
            
        Returns:
            List[Dict]: List of estimates
        """
        params = {
            "page": 1
        }
        if filter:
            params["filter"] = filter
            
        all_estimates = []
        while True:
            if limit != -1 and len(all_estimates) >= limit:
                break

            items = self._make_request("/customer_estimates", params=params)
            if len(items["estimates"]) > 0:
                params["page"] += 1
            else:
                break
            all_estimates.extend(items["estimates"])
            
        return all_estimates
    
    def get_estimate(self, estimate_id: str) -> Dict:
        """Get details for a specific estimate.
        
        Args:
            estimate_id (str): ID of the estimate to retrieve
            
        Returns:
            Dict: Estimate details
        """
        return self._make_request(f"/customer_estimates/{estimate_id}")
    
    def update_estimate(self, estimate_id: str, estimate_data: Dict) -> Dict:
        """Update a specific estimate.
        
        Args:
            estimate_id (str): ID of the estimate to update
            estimate_data (Dict): Updated estimate data
            
        Returns:
            Dict: Updated estimate details
        """
        return self._make_request(f"/customer_estimates/{estimate_id}", method="PUT", json={"invoice": estimate_data})
    
    def list_customers(
        self,
        limit: int = -1,
        filter: Optional[str] = None
    ) -> List[Dict]:
        """Get list of customers.
        
        Args:
            limit (int, optional): Number of customers to return. Defaults to -1 (all).
            filter (str, optional): Filter string in JSON format to filter customers.
                Example: '[{"field": "country_alpha2", "operator": "eq", "value": "FR"}]'
            
        Returns:
            List[Dict]: List of customers
        """
        params = {}
        if filter:
            params["filter"] = filter

        all_customers = []
        while True:
            if limit != -1 and len(all_customers) >= limit:
                break
                
            items = self._make_request("/customers", params=params)
            if len(items["customers"]) > 0:
                params["page"] += 1
            else:
                break
            all_customers.extend(items["customers"])
        return all_customers
    
    def get_customer_details(self, customer_id: str) -> Dict:
        """Get details for a specific customer.
        
        Args:
            customer_id (str): ID of the customer to retrieve
            
        Returns:
            Dict: Customer details
        """
        return self._make_request(f"/customers/{customer_id}")
    
    def update_customer(self, customer_id: str, **customer_data) -> Dict:
        """Update details for a specific customer.
        
        Args:
            customer_id (str): ID of the customer to update
            **customer_data: Arbitrary customer fields to update
            
        Returns:
            Dict: Updated customer details
        """
        return self._make_request(f"/customers/{customer_id}", method="PUT", json=customer_data)
    
    def list_products(
        self,
        limit: int = -1,
        page: Optional[int] = None
    ) -> List[Dict]:
        """Get list of products.
        
        Args:
            limit (int, optional): Number of products to return. Defaults to -1 (all).
            page (int, optional): Page number for paginated results.
            
        Returns:
            List[Dict]: List of products
        """
        params = {}
        if page is not None:
            params["page"] = page
            
        all_products = []
        while True:
            if limit != -1 and len(all_products) >= limit:
                break
                
            items = self._make_request("/products", params=params)
            if len(items["products"]) > 0:
                params["page"] += 1
            else:
                break
            all_products.extend(items["products"])
        return all_products
    
    def get_product(self, product_id: str) -> Dict:
        """Get details for a specific product.
        
        Args:
            product_id (str): ID of the product to retrieve
            
        Returns:
            Dict: Product details
        """
        return self._make_request(f"/products/{product_id}")
    
    def update_product(self, product_id: str, **product_data) -> Dict:
        """Update details for a specific product.
        
        Args:
            product_id (str): ID of the product to update
            **product_data: Arbitrary product fields to update
            
        Returns:
            Dict: Updated product details
        """
        return self._make_request(f"/products/{product_id}", method="PUT", json=product_data)
    
    def list_categories(
        self,
        sort: Optional[str] = None,
        filter: Optional[str] = None,
        limit: int = -1
    ) -> List[Dict]:
        """Get list of categories.
        
        Args:
            sort (str, optional): Sort categories by attributes (id, group_id, label, direction)
                                separated by commas
            filter (str, optional): Filter categories by attributes (id, group_id, label, direction)
                                  Example: [{"field": "direction", "operator": "eq", 
                                           "value": "cash_out"}]
            limit (int, optional): Total number of categories to return. Defaults to -1 (all).
            
        Returns:
            List[Dict]: List of categories
        """
        params = {
            "page": 1,
            "per_page": 20
        }
        if sort is not None:
            params["sort"] = sort
        if filter is not None:
            params["filter"] = filter
            
        all_categories = []
        while True:
            if limit != -1 and len(all_categories) >= limit:
                break
            items = self._make_request("/categories", params=params)
            if len(items["categories"]) > 0:
                params["page"] += 1
            else:
                break
            all_categories.extend(items["categories"])

        return all_categories

    def get_category(self, category_id: str) -> Dict:
        """Get details for a specific category.
        
        Args:
            category_id (str): ID of the category to retrieve
            
        Returns:
            Dict: Category details
        """
        return self._make_request(f"/categories/{category_id}")
    
    def update_category(self, category_id: str, category_data: Dict) -> Dict:
        """Update a specific category.
        
        Args:
            category_id (str): ID of the category to update
            category_data (Dict): Updated category data
            
        Returns:
            Dict: Updated category details
        """
        return self._make_request(f"/categories/{category_id}", method="PUT", json={"category": category_data})
    
    def list_plan_items(self, page: Optional[int] = None, per_page: Optional[int] = None) -> List[Dict]:
        """Get list of plan items with optional pagination.
        
        Args:
            page (int, optional): Page number for paginated results (starts at 1)
            per_page (int, optional): Number of plan items per page (defaults to 20)
            
        Returns:
            List[Dict]: List of plan items
        """
        params = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
            
        return self._make_request("/plan_items", params=params)
    
    def get_enum(self, enum_id: str, locale: str) -> Dict:
        """Get enum values for a specific identifier.
        
        Args:
            enum_id (str): Identifier of the enum to retrieve (e.g. 'countries', 'vat_rate')
            locale (str): Locale to use for the enum values
            
        Returns:
            Dict: Enum values
        """
        params = {"locale": locale}
        return self._make_request(f"/enums/{enum_id}", params=params)
    
    def list_suppliers(self, page: Optional[int] = None, limit: int = -1) -> List[Dict]:
        """Get list of suppliers.
        
        Args:
            page (int, optional): Page number for paginated results
            limit (int, optional): Number of suppliers to return. Defaults to -1 (all).
        Returns:
            List[Dict]: List of suppliers
        """
        params = {}
        if page is not None:
            params["page"] = page

        all_suppliers = []
        while True:
            if limit != -1 and len(all_suppliers) >= limit:
                break
                
            items = self._make_request("/suppliers", params=params)
            if len(items["suppliers"]) > 0:
                params["page"] += 1
            else:
                break
            all_suppliers.extend(items["suppliers"])
        return all_suppliers
    
    def get_supplier(self, supplier_id: str) -> Dict:
        """Get details for a specific supplier.
        
        Args:
            supplier_id (str): ID of the supplier to retrieve
            
        Returns:
            Dict: Supplier details
        """
        return self._make_request(f"/suppliers/{supplier_id}")
    
    def update_supplier(self, supplier_id: str, supplier_data: Dict) -> Dict:
        """Update a specific supplier.
        
        Args:
            supplier_id (str): ID of the supplier to update
            supplier_data (Dict): Updated supplier data
            
        Returns:
            Dict: Updated supplier details
        """
        return self._make_request(f"/suppliers/{supplier_id}", method="PUT", json={"supplier": supplier_data})
    
    def list_supplier_invoices(self, page: Optional[int] = None, per_page: Optional[int] = None, filter: Optional[str] = None) -> List[Dict]:
        """Get list of supplier invoices with optional pagination and filtering.
        
        Args:
            page (int, optional): Page number for paginated results (starts at 1)
            per_page (int, optional): Number of invoices per page (defaults to 20)
            filter (str, optional): Filter string for invoices. Example:
                '[{"field": "status", "operator": "scope", "value": "late_status"}]'
            
        Returns:
            List[Dict]: List of supplier invoices
        """
        params = {}
        if page is not None:
            params["page"] = page
        if per_page is not None:
            params["per_page"] = per_page
        if filter is not None:
            params["filter"] = filter
            
        return self._make_request("/supplier_invoices", params=params)
    
    def get_supplier_invoice(self, invoice_id: str) -> Dict:
        """Get details for a specific supplier invoice.
        
        Args:
            invoice_id (str): ID of the supplier invoice to retrieve
            
        Returns:
            Dict: Supplier invoice details
        """
        return self._make_request(f"/supplier_invoices/{invoice_id}")

    def update_supplier_invoice(self, invoice_id: str, invoice_data: Dict) -> Dict:
        """Update a specific supplier invoice.
        
        Args:
            invoice_id (str): ID of the supplier invoice to update
            invoice_data (Dict): Updated invoice data containing transaction reference 
                and categories
            
        Returns:
            Dict: Updated supplier invoice details
        """
        return self._make_request(f"/supplier_invoices/{invoice_id}", method="PUT", json={"invoice": invoice_data})

    
def as_tools(configuration: PennylaneIntegrationConfiguration):
    """Convert Pennylane integration into LangChain tools."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field
    
    integration = PennylaneIntegration(configuration)
    
    class ListCustomersInvoicesSchema(BaseModel):
        limit: int = Field(..., description="Number of invoices to return. Defaults to -1 (all).")
        filter: Optional[str] = Field(..., description="Filter string in JSON format to filter invoices. Example: '[{\"field\": \"status\", \"operator\": \"scope\", \"value\": \"late_status\"}]'")

    class GetCustomerInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to retrieve")

    class UpdateCustomerInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to update")
        transaction_reference: Optional[str] = Field(..., description="New transaction reference")
        categories: Optional[List[str]] = Field(..., description="List of category IDs to link to the invoice")

    class ListEstimatesSchema(BaseModel):
        limit: int = Field(..., description="Number of estimates to return. Defaults to -1 (all).")
        filter: Optional[str] = Field(..., description="Filter string in JSON format to filter estimates. Example: '[{\"field\": \"status\", \"operator\": \"scope\", \"value\": \"estimate_pending_status\"}]'")

    class GetEstimateSchema(BaseModel):
        estimate_id: str = Field(..., description="ID of the estimate to retrieve")

    class UpdateEstimateSchema(BaseModel):
        estimate_id: str = Field(..., description="ID of the estimate to update")
        estimate_data: Dict = Field(..., description="Updated estimate data")

    class ListCustomersSchema(BaseModel):
        limit: int = Field(..., description="Number of customers to return. Defaults to -1 (all).")
        filter: Optional[str] = Field(..., description="Filter string in JSON format to filter customers. Example: '[{\"field\": \"country_alpha2\", \"operator\": \"eq\", \"value\": \"FR\"}]'")

    class GetCustomerSchema(BaseModel):
        customer_id: str = Field(..., description="ID of the customer to retrieve")

    class UpdateCustomerSchema(BaseModel):
        customer_id: str = Field(..., description="ID of the customer to update")
        customer_data: Dict = Field(..., description="Updated customer data")

    class ListProductsSchema(BaseModel):
        limit: int = Field(..., description="Number of products to return. Defaults to -1 (all).")
        page: Optional[int] = Field(..., description="Page number for paginated results (starts at 1).")

    class GetProductSchema(BaseModel):
        product_id: str = Field(..., description="ID of the product to retrieve")

    class UpdateProductSchema(BaseModel):
        product_id: str = Field(..., description="ID of the product to update")
        product_data: Dict = Field(..., description="Updated product data")

    class ListCategoriesSchema(BaseModel):
        sort: Optional[str] = Field(..., description="Sort categories by attributes (id, group_id, label, direction) separated by commas.")
        filter: Optional[str] = Field(..., description="Filter categories by attributes (id, group_id, label, direction). Example: '[{\"field\": \"direction\", \"operator\": \"eq\", \"value\": \"cash_out\"}]'")
        limit: int = Field(..., description="Total number of categories to return. Defaults to -1 (all).")

    class GetCategorySchema(BaseModel):
        category_id: str = Field(..., description="ID of the category to retrieve")

    class UpdateCategorySchema(BaseModel):
        category_id: str = Field(..., description="ID of the category to update")
        category_data: Dict = Field(..., description="Updated category data")

    class ListPlanItemsSchema(BaseModel):
        page: Optional[int] = Field(..., description="Page number for paginated results (starts at 1).")
        per_page: Optional[int] = Field(..., description="Number of plan items per page (defaults to 20).")

    class GetEnumSchema(BaseModel):
        enum_id: str = Field(..., description="Identifier of the enum to retrieve (e.g. 'countries', 'vat_rate')")
        locale: str = Field(..., description="Locale to use for the enum values")

    class ListSuppliersSchema(BaseModel):
        page: Optional[int] = Field(..., description="Page number for paginated results (starts at 1).")
        limit: int = Field(..., description="Total number of suppliers to return. Defaults to -1 (all).")

    class GetSupplierSchema(BaseModel):
        supplier_id: str = Field(..., description="ID of the supplier to retrieve")

    class UpdateSupplierSchema(BaseModel):
        supplier_id: str = Field(..., description="ID of the supplier to update")
        supplier_data: Dict = Field(..., description="Updated supplier data")

    class ListSupplierInvoicesSchema(BaseModel):
        page: Optional[int] = Field(..., description="Page number for paginated results (starts at 1).")
        per_page: Optional[int] = Field(..., description="Number of invoices per page (defaults to 20).")
        filter: Optional[str] = Field(..., description="Filter string for invoices. Example: '[{\"field\": \"status\", \"operator\": \"scope\", \"value\": \"late_status\"}]'")

    class GetSupplierInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the supplier invoice to retrieve")

    class UpdateSupplierInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the supplier invoice to update")
        invoice_data: Dict = Field(..., description="Updated invoice data containing transaction reference and categories")

    return [
        StructuredTool(
            name="list_customers_invoices",
            description="List customer invoices from Pennylane.",
            func=lambda limit, filter: integration.list_customer_invoices(limit, filter),
            args_schema=ListCustomersInvoicesSchema
        ),
        StructuredTool(
            name="get_customer_invoice",
            description="Get a specific customer invoice from Pennylane.",
            func=lambda invoice_id: integration.get_customer_invoice(invoice_id),
            args_schema=GetCustomerInvoiceSchema
        ),
        StructuredTool(
            name="update_customer_invoice",
            description="Update a specific customer invoice from Pennylane.",
            func=lambda invoice_id, transaction_reference, categories: integration.update_customer_invoice(invoice_id, transaction_reference, categories),
            args_schema=UpdateCustomerInvoiceSchema
        ),
        StructuredTool(
            name="list_estimates",
            description="List customer estimates from Pennylane.",
            func=lambda limit, filter: integration.list_estimates(limit, filter),
            args_schema=ListEstimatesSchema
        ),
        StructuredTool(
            name="get_estimate",
            description="Get a specific estimate from Pennylane.",
            func=lambda estimate_id: integration.get_estimate(estimate_id),
            args_schema=GetEstimateSchema
        ),
        StructuredTool(
            name="update_estimate",
            description="Update a specific estimate from Pennylane.",
            func=lambda estimate_id, estimate_data: integration.update_estimate(estimate_id, estimate_data),
            args_schema=UpdateEstimateSchema
        ),
        StructuredTool(
            name="list_customers",
            description="List customers from Pennylane.",
            func=lambda limit, filter: integration.list_customers(limit, filter),
            args_schema=ListCustomersSchema
        ),
        StructuredTool(
            name="get_customer",
            description="Get a specific customer from Pennylane.",
            func=lambda customer_id: integration.get_customer_details(customer_id),
            args_schema=GetCustomerSchema
        ),
        StructuredTool(
            name="update_customer",
            description="Update a specific customer from Pennylane.",
            func=lambda customer_id, customer_data: integration.update_customer(customer_id, customer_data),
            args_schema=UpdateCustomerSchema
        ),
        StructuredTool(
            name="list_products",
            description="List products from Pennylane.",
            func=lambda limit, page: integration.list_products(limit, page),
            args_schema=ListProductsSchema
        ),
        StructuredTool(
            name="get_product",
            description="Get a specific product from Pennylane.",
            func=lambda product_id: integration.get_product(product_id),
            args_schema=GetProductSchema
        ),
        StructuredTool(
            name="update_product",
            description="Update a specific product from Pennylane.",
            func=lambda product_id, product_data: integration.update_product(product_id, product_data),
            args_schema=UpdateProductSchema
        ),
        StructuredTool(
            name="list_categories",
            description="List categories from Pennylane.",
            func=lambda sort, filter, limit: integration.list_categories(sort, filter, limit),
            args_schema=ListCategoriesSchema
        ), 
        StructuredTool(
            name="get_category",
            description="Get a specific category from Pennylane.",
            func=lambda category_id: integration.get_category(category_id),
            args_schema=GetCategorySchema
        ),
        StructuredTool(
            name="update_category",
            description="Update a specific category from Pennylane.",
            func=lambda category_id, category_data: integration.update_category(category_id, category_data),
            args_schema=UpdateCategorySchema
        ),
        StructuredTool(
            name="list_plan_items",
            description="List plan items from Pennylane.",
            func=lambda page, per_page: integration.list_plan_items(page, per_page),
            args_schema=ListPlanItemsSchema
        ),
        StructuredTool(
            name="get_enum",
            description="Get enum values for a specific identifier from Pennylane.",
            func=lambda enum_id, locale: integration.get_enum(enum_id, locale),
            args_schema=GetEnumSchema
        ),
        StructuredTool(
            name="list_suppliers",
            description="List suppliers from Pennylane.",
            func=lambda page, limit: integration.list_suppliers(page, limit),
            args_schema=ListSuppliersSchema
        ),  
        StructuredTool(
            name="get_supplier",
            description="Get a specific supplier from Pennylane.",
            func=lambda supplier_id: integration.get_supplier(supplier_id),
            args_schema=GetSupplierSchema
        ),
        StructuredTool(
            name="update_supplier",
            description="Update a specific supplier from Pennylane.",
            func=lambda supplier_id, supplier_data: integration.update_supplier(supplier_id, supplier_data),
            args_schema=UpdateSupplierSchema
        ),
        StructuredTool(
            name="list_supplier_invoices",
            description="List supplier invoices from Pennylane.",
            func=lambda page, per_page, filter: integration.list_supplier_invoices(page, per_page, filter),
            args_schema=ListSupplierInvoicesSchema
        ),
        StructuredTool(
            name="get_supplier_invoice",
            description="Get a specific supplier invoice from Pennylane.",
            func=lambda invoice_id: integration.get_supplier_invoice(invoice_id),
            args_schema=GetSupplierInvoiceSchema
        ),
        StructuredTool(
            name="update_supplier_invoice",
            description="Update a specific supplier invoice from Pennylane.",
            func=lambda invoice_id, invoice_data: integration.update_supplier_invoice(invoice_id, invoice_data),
            args_schema=UpdateSupplierInvoiceSchema
        )
    ]