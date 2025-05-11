import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from dataclasses import dataclass
from pydantic import BaseModel, Field
from lib.abi.integration.integration import (
    Integration,
    IntegrationConnectionError,
    IntegrationConfiguration,
)

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
    More info: https://stripe.com/docs/api
    """

    __configuration: StripeIntegrationConfiguration

    def __init__(self, configuration: StripeIntegrationConfiguration):
        """Initialize Stripe client with API key."""
        super().__init__(configuration)
        self.__configuration = configuration

        self.headers = {
            "Authorization": f"Bearer {self.__configuration.api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

    def _make_request(
        self, method: str, endpoint: str, params: Dict = None, data: Dict = None
    ) -> Dict:
        """Make HTTP request to Stripe API."""
        url = f"{self.__configuration.base_url}{endpoint}"
        try:
            response = requests.request(
                method=method, url=url, headers=self.headers, params=params, data=data
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
            data = response["data"]
            customers.extend(data)

            for customer in data:
                if customer.get("email") == email:
                    return customer

            has_more = response["has_more"]
            if has_more:
                last_customer_id = customers[-1]["id"]
                url = f"/customers?starting_after={last_customer_id}"

        return None

    def get_customers(
        self,
        limit: int = 100,
        start_date: Optional[datetime] = None,
        hours_ago: Optional[int] = None,
        days_ago: Optional[int] = None,
        end_date: Optional[datetime] = None,
    ) -> List[Dict]:
        """Get list of customers with optional filters.

        Args:
            limit (int): Maximum number of customers to return
            start_date (datetime, optional): Filter customers created after this date
            hours_ago (int, optional): Get customers from this many hours ago
            days_ago (int, optional): Get customers from this many days ago
            end_date (datetime, optional): Filter customers created before this date
        """
        params = {"limit": limit}

        if start_date:
            params["created[gte]"] = int(start_date.timestamp())
        elif hours_ago is not None:
            start_date = datetime.now() - timedelta(hours=hours_ago)
            params["created[gte]"] = int(start_date.timestamp())
        elif days_ago is not None:
            start_date = datetime.now() - timedelta(days=days_ago)
            params["created[gte]"] = int(start_date.timestamp())

        if end_date:
            params["created[lte]"] = int(end_date.timestamp())

        customers = []
        url = "/customers"
        has_more = True

        while has_more:
            response = self._make_request("GET", url, params=params)
            customers.extend(response["data"])
            has_more = response["has_more"]

            if has_more:
                last_customer_id = customers[-1]["id"]
                url = f"/customers?starting_after={last_customer_id}"

        return customers

    def create_customer(self, email: str, metadata: Dict) -> Dict:
        """Create a new customer."""
        data = {"email": email, **metadata}
        return self._make_request("POST", "/customers", data=data)

    def update_customer(self, customer_id: str, data: Dict) -> Dict:
        """Update an existing customer."""
        return self._make_request("POST", f"/customers/{customer_id}", data=data)

    def list_customer_payment_methods(self, customer_id: str) -> Dict:
        """Get the payment methods of a specific customer."""
        return self._make_request("GET", f"/customers/{customer_id}/payment_methods")

    def get_products(self) -> Dict:
        """Get the products of the account."""
        return self._make_request("/products")

    def get_product(self, product_id: str) -> Dict:
        """Get the product of the account."""
        return self._make_request(f"/products/{product_id}")

    def create_product(self, data: Dict) -> Dict:
        """Create a new product."""
        return self._make_request("POST", "/products", data=data)

    def update_product(self, product_id: str, data: Dict) -> Dict:
        """Update an existing product."""
        return self._make_request("POST", f"/products/{product_id}", data=data)

    def delete_product(self, product_id: str) -> Dict:
        """Delete an existing product."""
        return self._make_request("DELETE", f"/products/{product_id}")

    def get_subscriptions(self) -> Dict:
        """Get the subscriptions of the account."""
        return self._make_request("/subscriptions")

    def get_subscription(self, subscription_id: str) -> Dict:
        """Get the subscription of the account."""
        return self._make_request(f"/subscriptions/{subscription_id}")

    def create_subscription(self, data: Dict) -> Dict:
        """Create a new subscription."""
        return self._make_request("POST", "/subscriptions", data=data)

    def update_subscription(self, subscription_id: str, data: Dict) -> Dict:
        """Update an existing subscription."""
        return self._make_request(
            "POST", f"/subscriptions/{subscription_id}", data=data
        )

    def delete_subscription(self, subscription_id: str) -> Dict:
        """Delete an existing subscription."""
        return self._make_request("DELETE", f"/subscriptions/{subscription_id}")

    def get_balance(self) -> Dict:
        """Get the balance of the account."""
        return self._make_request("/balance")

    def get_balance_transactions(self) -> Dict:
        """Get the balance transactions of the account."""
        return self._make_request("/balance_transactions")

    def get_balance_transaction(self, transaction_id: str) -> Dict:
        """Get the balance transaction of the account."""
        return self._make_request(f"/balance_transactions/{transaction_id}")

    def get_invoices(
        self,
        customer: str = None,
        status: str = None,
        subscription: str = None,
        collection_method: str = None,
        created: Dict = None,
        ending_before: str = None,
        limit: int = None,
        starting_after: str = None,
    ) -> Dict:
        """Get the invoices of the account.

        Args:
            customer (str, optional): Only return invoices for this customer ID
            status (str, optional): Invoice status - one of 'draft', 'open', 'paid', 'uncollectible', or 'void'
            subscription (str, optional): Only return invoices for this subscription ID
            collection_method (str, optional): Collection method for the invoices
            created (Dict, optional): Filter by invoice creation date
            ending_before (str, optional): Cursor for pagination - get items before this ID
            limit (int, optional): Maximum number of invoices to return
            starting_after (str, optional): Cursor for pagination - get items after this ID

        Returns:
            Dict: List of invoices matching the criteria
        """
        params = {
            "customer": customer,
            "status": status,
            "subscription": subscription,
            "collection_method": collection_method,
            "created": created,
            "ending_before": ending_before,
            "limit": limit,
            "starting_after": starting_after,
        }
        # Remove None values
        params = {k: v for k, v in params.items() if v is not None}

        return self._make_request("GET", "/invoices", data=params)

    def get_invoice(self, invoice_id: str) -> Dict:
        """Get the invoice of the account."""
        return self._make_request(f"/invoices/{invoice_id}")

    def create_invoice(self, data: Dict) -> Dict:
        """Create a new invoice."""
        return self._make_request("POST", "/invoices", data=data)

    def update_invoice(self, invoice_id: str, data: Dict) -> Dict:
        """Update an existing invoice."""
        return self._make_request("POST", f"/invoices/{invoice_id}", data=data)

    def delete_invoice(self, invoice_id: str) -> Dict:
        """Delete an existing invoice."""
        return self._make_request("DELETE", f"/invoices/{invoice_id}")

    def get_invoice_items(self) -> Dict:
        """Get the invoice items of the account."""
        return self._make_request("/invoiceitems")

    def get_payment_methods(self) -> Dict:
        """Get the payment methods of the account."""
        return self._make_request("/payment_methods")

    def get_payment_method(self, payment_method_id: str) -> Dict:
        """Get the payment method of the account."""
        return self._make_request(f"/payment_methods/{payment_method_id}")

    def create_payment_method(self, data: Dict) -> Dict:
        """Create a new payment method."""
        return self._make_request("POST", "/payment_methods", data=data)

    def update_payment_method(self, payment_method_id: str, data: Dict) -> Dict:
        """Update an existing payment method."""
        return self._make_request(
            "POST", f"/payment_methods/{payment_method_id}", data=data
        )

    def delete_payment_method(self, payment_method_id: str) -> Dict:
        """Delete an existing payment method."""
        return self._make_request("DELETE", f"/payment_methods/{payment_method_id}")

    def get_customer_payment_methods(self, customer_id: str) -> Dict:
        """Get the payment methods of a specific customer."""
        return self._make_request(f"/customers/{customer_id}/payment_methods")

    def get_payment_method_details(
        self, customer_id: str, payment_method_id: str
    ) -> Dict:
        """Get the details of a specific payment method."""
        return self._make_request(
            f"/customers/{customer_id}/payment_methods/{payment_method_id}"
        )


def as_tools(configuration: StripeIntegrationConfiguration):
    from langchain_core.tools import StructuredTool

    integration = StripeIntegration(configuration)

    class GetCustomerSchema(BaseModel):
        email: str = Field(..., description="Email of the customer to find")

    class GetCustomersSchema(BaseModel):
        limit: int = Field(100, description="Maximum number of customers to return")
        start_date: Optional[datetime] = Field(
            None,
            description="Get customers created after this date. If not provided, get customers from this many hours ago or days ago.",
        )
        hours_ago: Optional[int] = Field(
            None, description="Get customers from this many hours ago"
        )
        days_ago: Optional[int] = Field(
            None, description="Get customers from this many days ago"
        )
        end_date: Optional[datetime] = Field(
            None, description="Filter customers created before this date"
        )

    class CreateCustomerSchema(BaseModel):
        email: str = Field(..., description="Email of the new customer")
        metadata: Dict = Field(..., description="Additional customer metadata")

    class UpdateCustomerSchema(BaseModel):
        customer_id: str = Field(..., description="ID of the customer to update")
        data: Dict = Field(..., description="Data to update for the customer")

    class ListCustomerPaymentMethodsSchema(BaseModel):
        customer_id: str = Field(
            ..., description="ID of the customer to get the payment methods"
        )

    class GetProductsSchema(BaseModel):
        pass

    class GetProductSchema(BaseModel):
        product_id: str = Field(..., description="ID of the product to get")

    class CreateProductSchema(BaseModel):
        data: Dict = Field(..., description="Data to create the product")

    class UpdateProductSchema(BaseModel):
        product_id: str = Field(..., description="ID of the product to update")
        data: Dict = Field(..., description="Data to update the product")

    class DeleteProductSchema(BaseModel):
        product_id: str = Field(..., description="ID of the product to delete")

    class GetSubscriptionsSchema(BaseModel):
        pass

    class GetSubscriptionSchema(BaseModel):
        subscription_id: str = Field(..., description="ID of the subscription to get")

    class CreateSubscriptionSchema(BaseModel):
        data: Dict = Field(..., description="Data to create the subscription")

    class UpdateSubscriptionSchema(BaseModel):
        subscription_id: str = Field(
            ..., description="ID of the subscription to update"
        )
        data: Dict = Field(..., description="Data to update the subscription")

    class DeleteSubscriptionSchema(BaseModel):
        subscription_id: str = Field(
            ..., description="ID of the subscription to delete"
        )

    class GetInvoicesSchema(BaseModel):
        pass

    class GetInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to get")

    class CreateInvoiceSchema(BaseModel):
        data: Dict = Field(..., description="Data to create the invoice")

    class UpdateInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to update")
        data: Dict = Field(..., description="Data to update the invoice")

    class DeleteInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to delete")

    class GetInvoiceItemsSchema(BaseModel):
        pass

    class GetPaymentMethodsSchema(BaseModel):
        pass

    class GetPaymentMethodSchema(BaseModel):
        payment_method_id: str = Field(
            ..., description="ID of the payment method to get"
        )

    class CreatePaymentMethodSchema(BaseModel):
        data: Dict = Field(..., description="Data to create the payment method")

    class UpdatePaymentMethodSchema(BaseModel):
        payment_method_id: str = Field(
            ..., description="ID of the payment method to update"
        )
        data: Dict = Field(..., description="Data to update the payment method")

    class DeletePaymentMethodSchema(BaseModel):
        payment_method_id: str = Field(
            ..., description="ID of the payment method to delete"
        )

    class GetCustomerPaymentMethodsSchema(BaseModel):
        customer_id: str = Field(
            ..., description="ID of the customer to get the payment methods"
        )

    class GetPaymentMethodDetailsSchema(BaseModel):
        customer_id: str = Field(
            ..., description="ID of the customer to get the payment method details"
        )
        payment_method_id: str = Field(
            ..., description="ID of the payment method to get the details"
        )

    return [
        StructuredTool(
            name="get_stripe_customer",
            description="Get a Stripe customer by email",
            func=lambda email: integration.get_customer(email),
            args_schema=GetCustomerSchema,
        ),
        StructuredTool(
            name="stripe_list_customers",
            description="Get list of Stripe customers with optional filters.",
            func=lambda limit=100,
            start_date=None,
            hours_ago=None,
            days_ago=None,
            end_date=None: integration.get_customers(
                limit, start_date, hours_ago, days_ago, end_date
            ),
            args_schema=GetCustomersSchema,
        ),
        StructuredTool(
            name="stripe_create_customer",
            description="Create a new Stripe customer",
            func=lambda email, metadata: integration.create_customer(email, metadata),
            args_schema=CreateCustomerSchema,
        ),
        StructuredTool(
            name="stripe_update_customer",
            description="Update an existing Stripe customer",
            func=lambda customer_id, data: integration.update_customer(
                customer_id, data
            ),
            args_schema=UpdateCustomerSchema,
        ),
        StructuredTool(
            name="stripe_list_customer_payment_methods",
            description="List the payment methods of a specific customer",
            func=lambda customer_id: integration.list_customer_payment_methods(
                customer_id
            ),
            args_schema=ListCustomerPaymentMethodsSchema,
        ),
        StructuredTool(
            name="stripe_get_products",
            description="Get the products of the account",
            func=lambda: integration.get_products(),
            args_schema=GetProductsSchema,
        ),
        StructuredTool(
            name="stripe_get_product",
            description="Get the product of the account",
            func=lambda product_id: integration.get_product(product_id),
            args_schema=GetProductSchema,
        ),
        StructuredTool(
            name="stripe_create_product",
            description="Create a new Stripe product",
            func=lambda data: integration.create_product(data),
            args_schema=CreateProductSchema,
        ),
        StructuredTool(
            name="stripe_update_product",
            description="Update an existing Stripe product",
            func=lambda product_id, data: integration.update_product(product_id, data),
            args_schema=UpdateProductSchema,
        ),
        StructuredTool(
            name="stripe_delete_product",
            description="Delete an existing Stripe product",
            func=lambda product_id: integration.delete_product(product_id),
            args_schema=DeleteProductSchema,
        ),
        StructuredTool(
            name="stripe_get_subscriptions",
            description="Get the subscriptions of the account",
            func=lambda: integration.get_subscriptions(),
            args_schema=GetSubscriptionsSchema,
        ),
        StructuredTool(
            name="stripe_get_subscription",
            description="Get the subscription of the account",
            func=lambda subscription_id: integration.get_subscription(subscription_id),
            args_schema=GetSubscriptionSchema,
        ),
        StructuredTool(
            name="stripe_create_subscription",
            description="Create a new Stripe subscription",
            func=lambda data: integration.create_subscription(data),
            args_schema=CreateSubscriptionSchema,
        ),
        StructuredTool(
            name="stripe_update_subscription",
            description="Update an existing Stripe subscription",
            func=lambda subscription_id, data: integration.update_subscription(
                subscription_id, data
            ),
            args_schema=UpdateSubscriptionSchema,
        ),
        StructuredTool(
            name="stripe_delete_subscription",
            description="Delete an existing Stripe subscription",
            func=lambda subscription_id: integration.delete_subscription(
                subscription_id
            ),
            args_schema=DeleteSubscriptionSchema,
        ),
        StructuredTool(
            name="stripe_get_invoices",
            description="Get the invoices of the account",
            func=lambda: integration.get_invoices(),
            args_schema=GetInvoicesSchema,
        ),
        StructuredTool(
            name="stripe_get_invoice",
            description="Get the invoice of the account",
            func=lambda invoice_id: integration.get_invoice(invoice_id),
            args_schema=GetInvoiceSchema,
        ),
        StructuredTool(
            name="stripe_create_invoice",
            description="Create a new Stripe invoice",
            func=lambda data: integration.create_invoice(data),
            args_schema=CreateInvoiceSchema,
        ),
        StructuredTool(
            name="stripe_update_invoice",
            description="Update an existing Stripe invoice",
            func=lambda invoice_id, data: integration.update_invoice(invoice_id, data),
            args_schema=UpdateInvoiceSchema,
        ),
        StructuredTool(
            name="stripe_delete_invoice",
            description="Delete an existing Stripe invoice",
            func=lambda invoice_id: integration.delete_invoice(invoice_id),
            args_schema=DeleteInvoiceSchema,
        ),
        StructuredTool(
            name="stripe_get_invoice_items",
            description="Get the invoice items of the account",
            func=lambda: integration.get_invoice_items(),
            args_schema=GetInvoiceItemsSchema,
        ),
        StructuredTool(
            name="stripe_get_payment_methods",
            description="Get the payment methods of the account",
            func=lambda: integration.get_payment_methods(),
            args_schema=GetPaymentMethodsSchema,
        ),
        StructuredTool(
            name="stripe_get_payment_method",
            description="Get the payment method of the account",
            func=lambda payment_method_id: integration.get_payment_method(
                payment_method_id
            ),
            args_schema=GetPaymentMethodSchema,
        ),
        StructuredTool(
            name="stripe_create_payment_method",
            description="Create a new Stripe payment method",
            func=lambda data: integration.create_payment_method(data),
            args_schema=CreatePaymentMethodSchema,
        ),
        StructuredTool(
            name="stripe_update_payment_method",
            description="Update an existing Stripe payment method",
            func=lambda payment_method_id, data: integration.update_payment_method(
                payment_method_id, data
            ),
            args_schema=UpdatePaymentMethodSchema,
        ),
        StructuredTool(
            name="stripe_delete_payment_method",
            description="Delete an existing Stripe payment method",
            func=lambda payment_method_id: integration.delete_payment_method(
                payment_method_id
            ),
            args_schema=DeletePaymentMethodSchema,
        ),
        StructuredTool(
            name="stripe_get_customer_payment_methods",
            description="Get the payment methods of a specific customer",
            func=lambda customer_id: integration.get_customer_payment_methods(
                customer_id
            ),
            args_schema=GetCustomerPaymentMethodsSchema,
        ),
        StructuredTool(
            name="stripe_get_payment_method_details",
            description="Get the details of a specific payment method",
            func=lambda customer_id,
            payment_method_id: integration.get_payment_method_details(
                customer_id, payment_method_id
            ),
            args_schema=GetPaymentMethodDetailsSchema,
        ),
    ]
