import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from datetime import datetime
from dataclasses import dataclass
from pydantic import BaseModel, Field
from lib.abi.integration.integration import Integration, IntegrationConnectionError, IntegrationConfiguration

LOGO_URL = "https://logo.clearbit.com/stripe.com"

@dataclass
class StripeIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for Stripe integration.
    
    Attributes:
        api_key (str): Stripe API key for authentication
        base_url (str): Base URL for Stripe API
    """
    api_key: str
    base_url: str = "https://api.stripe.com/v1"

class StripeIntegration(Integration):
    """Stripe API integration client.
    
    This integration provides methods to interact with Stripe's API endpoints.
    It handles authentication and request management.
    """

    __configuration: StripeIntegrationConfiguration

    def __init__(self, configuration: StripeIntegrationConfiguration):
        """Initialize Stripe client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration
        
        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/x-www-form-urlencoded"
        }

    def _make_request(self, method: str, endpoint: str, params: Dict = None, data: Dict = None) -> Dict:
        """Make HTTP request to Stripe API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                data=data
            )
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise IntegrationConnectionError(f"Stripe API request failed: {str(e)}")

    def get_customer(self, email: str) -> Optional[Dict]:
        """Get customer by email."""
        customers = []
        url = "/customers"
        has_more = True
        
        while has_more:
            response = self._make_request("GET", url)
            data = response['data']
            customers.extend(data)
            
            for customer in data:
                if customer.get("email") == email:
                    return customer
                    
            has_more = response['has_more']
            if has_more:
                last_customer_id = customers[-1]['id']
                url = f"/customers?starting_after={last_customer_id}"
                
        return None

    def get_customers(self, limit: int = 100, start_date: Optional[datetime] = None,
                     hours_ago: Optional[int] = None, days_ago: Optional[int] = None,
                     end_date: Optional[datetime] = None) -> List[Dict]:
        """Get list of customers with optional filters.
        
        Args:
            limit (int): Maximum number of customers to return
            start_date (datetime, optional): Filter customers created after this date
            hours_ago (int, optional): Get customers from this many hours ago
            days_ago (int, optional): Get customers from this many days ago
            end_date (datetime, optional): Filter customers created before this date
        """
        params = {'limit': limit}
        
        if start_date:
            params['created[gte]'] = int(start_date.timestamp())
        elif hours_ago is not None:
            start_date = datetime.now() - timedelta(hours=hours_ago)
            params['created[gte]'] = int(start_date.timestamp())
        elif days_ago is not None:
            start_date = datetime.now() - timedelta(days=days_ago)
            params['created[gte]'] = int(start_date.timestamp())
            
        if end_date:
            params['created[lte]'] = int(end_date.timestamp())
            
        customers = []
        url = "/customers"
        has_more = True
        
        while has_more:
            response = self._make_request("GET", url, params=params)
            customers.extend(response['data'])
            has_more = response['has_more']
            
            if has_more:
                last_customer_id = customers[-1]['id']
                url = f"/customers?starting_after={last_customer_id}"
                
        return customers

    def create_customer(self, email: str, metadata: Dict) -> Dict:
        """Create a new customer."""
        data = {'email': email, **metadata}
        return self._make_request("POST", "/customers", data=data)

    def update_customer(self, customer_id: str, data: Dict) -> Dict:
        """Update an existing customer."""
        return self._make_request("POST", f"/customers/{customer_id}", data=data)

def as_tools(configuration: StripeIntegrationConfiguration):
    from langchain_core.tools import StructuredTool
    
    integration = StripeIntegration(configuration)

    class GetCustomerSchema(BaseModel):
        email: str = Field(..., description="Email of the customer to find")

    class GetCustomersSchema(BaseModel):
        limit: int = Field(100, description="Maximum number of customers to return")
        start_date: Optional[datetime] = Field(None, description="Get customers created after this date. If not provided, get customers from this many hours ago or days ago.")
        hours_ago: Optional[int] = Field(None, description="Get customers from this many hours ago")
        days_ago: Optional[int] = Field(None, description="Get customers from this many days ago")
        end_date: Optional[datetime] = Field(None, description="Filter customers created before this date")

    class CreateCustomerSchema(BaseModel):
        email: str = Field(..., description="Email of the new customer")
        metadata: Dict = Field(..., description="Additional customer metadata")

    class UpdateCustomerSchema(BaseModel):
        customer_id: str = Field(..., description="ID of the customer to update")
        data: Dict = Field(..., description="Data to update for the customer")

    return [
        StructuredTool(
            name="get_stripe_customer",
            description="Get a Stripe customer by email",
            func=lambda email: integration.get_customer(email),
            args_schema=GetCustomerSchema
        ),
        StructuredTool(
            name="get_stripe_customers",
            description="Get list of Stripe customers with optional filters.",
            func=lambda limit=100, start_date=None, hours_ago=None, days_ago=None, end_date=None: 
                integration.get_customers(limit, start_date, hours_ago, days_ago, end_date),
            args_schema=GetCustomersSchema
        ),
        StructuredTool(
            name="create_stripe_customer",
            description="Create a new Stripe customer",
            func=lambda email, metadata: integration.create_customer(email, metadata),
            args_schema=CreateCustomerSchema
        ),
        StructuredTool(
            name="update_stripe_customer",
            description="Update an existing Stripe customer",
            func=lambda customer_id, data: integration.update_customer(customer_id, data),
            args_schema=UpdateCustomerSchema
        )
    ] 