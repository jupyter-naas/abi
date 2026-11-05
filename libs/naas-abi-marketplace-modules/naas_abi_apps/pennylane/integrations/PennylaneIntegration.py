"""Pennylane external API (v2), async, on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.pennylane.integrations``: same
endpoints and tool names. Each list or get result is also written as JSON to
object storage under ``datastore_path`` when a storage is given.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Protocol

import httpx
from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)

DEFAULT_BASE_URL = "https://app.pennylane.com/api/external"
PAGE_SIZE = 100


class ObjectStorage(Protocol):
    """What the integration needs from ``engine.services.object_storage``."""

    async def put_object(self, prefix: str, key: str, content: bytes) -> None: ...


@dataclass
class PennylaneIntegrationConfiguration(IntegrationConfiguration):
    """api_key: Pennylane API token. storage: where results are archived
    (``None``: not archived). transport: an httpx transport, for tests."""

    api_key: str
    base_url: str = DEFAULT_BASE_URL
    datastore_path: str = "pennylane"
    storage: ObjectStorage | None = None
    timeout: float = 60.0
    transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)


def _filter_suffix(filters: list[dict[str, Any]]) -> str:
    return "_".join(f"filter_[{json.dumps(f)}]" for f in filters).replace(" ", "_")


class PennylaneIntegration(Integration):
    """Pennylane API client: customers, customer invoices, categories, transactions."""

    def __init__(self, configuration: PennylaneIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration
        self.headers = {
            "Authorization": f"Bearer {configuration.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    async def _request(
        self,
        endpoint: str,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        url = f"{self.configuration.base_url}/{endpoint}"
        try:
            async with httpx.AsyncClient(
                timeout=self.configuration.timeout,
                transport=self.configuration.transport,
            ) as client:
                response = await client.request(
                    method, url, headers=self.headers, json=body, params=params
                )
                response.raise_for_status()
                return response.json()
        except httpx.HTTPError as exc:
            raise IntegrationConnectionError(
                f"Pennylane API request failed: {exc!s}"
            ) from exc

    async def _get_all_items(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> list[Any]:
        """Follow ``next_cursor`` until ``has_more`` is false."""
        params = dict(params or {})
        items: list[Any] = []
        while True:
            page = await self._request(endpoint, params=params)
            items.extend(page.get("items") or [])
            if not page.get("has_more"):
                return items
            params["cursor"] = page.get("next_cursor")

    async def _archive(self, value: Any, folder: str, file_name: str) -> None:
        storage = self.configuration.storage
        if storage is None:
            return
        prefix = f"{self.configuration.datastore_path}/{folder}"
        content = json.dumps(value, indent=4, ensure_ascii=False).encode("utf-8")
        await storage.put_object(prefix, file_name, content)

    async def _list(
        self,
        endpoint: str,
        name: str,
        sort: str,
        filters: list[dict[str, Any]] | None,
    ) -> list[Any]:
        filters = list(filters or [])
        params: dict[str, Any] = {"limit": PAGE_SIZE, "sort": sort}
        if filters:
            params["filter"] = json.dumps(filters)
        items = await self._get_all_items(endpoint, params=params)
        suffix = _filter_suffix(filters)
        await self._archive(
            items, name, f"{name}_{suffix}.json" if suffix else f"{name}.json"
        )
        return items

    async def list_customers(
        self, sort: str = "-id", filters: list[dict[str, Any]] | None = None
    ) -> list[Any]:
        """List customers. filters: e.g. ``[{"field": "country_alpha2", "operator": "eq", "value": "FR"}]``."""
        return await self._list("v2/customers", "list_customers", sort, filters)

    async def get_customer(self, customer_id: str) -> dict[str, Any]:
        """Details of one customer."""
        customer = await self._request(f"v2/customers/{customer_id}")
        await self._archive(
            customer, f"get_customer/{customer_id}", f"{customer_id}.json"
        )
        return customer

    async def list_customer_invoices(
        self,
        sort: str = "-date",
        filters: list[dict[str, Any]] | None = None,
        customer_id: str | None = None,
        start_date: str | None = None,
    ) -> list[Any]:
        """List customer invoices, optionally for one customer and from a date (YYYY-MM-DD)."""
        filters = list(filters or [])
        if customer_id:
            filters.append(
                {"field": "customer_id", "operator": "match", "value": customer_id}
            )
        if start_date:
            filters.append({"field": "date", "operator": "gteq", "value": start_date})
        return await self._list(
            "v2/customer_invoices", "list_customer_invoices", sort, filters
        )

    async def get_customer_invoice(self, invoice_id: str) -> dict[str, Any]:
        """One customer invoice."""
        invoice = await self._request(f"v2/customer_invoices/{invoice_id}")
        await self._archive(
            invoice, f"get_customer_invoice/{invoice_id}", f"{invoice_id}.json"
        )
        return invoice

    async def get_customer_invoice_categories(self, invoice_id: str) -> list[Any]:
        """Categories of one customer invoice."""
        categories = await self._get_all_items(
            f"v2/customer_invoices/{invoice_id}/categories"
        )
        await self._archive(
            categories,
            f"get_customer_invoice_categories/{invoice_id}",
            f"{invoice_id}.json",
        )
        return categories

    async def list_categories(
        self, sort: str = "-id", filters: list[dict[str, Any]] | None = None
    ) -> list[Any]:
        """List analytical categories."""
        return await self._list("v2/categories", "list_categories", sort, filters)

    async def list_category_groups(self) -> list[Any]:
        """List category groups."""
        groups = await self._get_all_items(
            "v2/category_groups", params={"limit": PAGE_SIZE}
        )
        await self._archive(groups, "list_category_groups", "list_category_groups.json")
        return groups

    async def list_bank_transactions(
        self, sort: str = "-id", filters: list[dict[str, Any]] | None = None
    ) -> list[Any]:
        """List bank transactions."""
        return await self._list(
            "v2/transactions", "list_bank_transactions", sort, filters
        )


def as_tools(configuration: PennylaneIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration (needs ``naas-abi-sdk[agent]``)."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = PennylaneIntegration(configuration)

    class ListCustomersSchema(BaseModel):
        pass

    class GetCustomerDetailsSchema(BaseModel):
        customer_id: str = Field(..., description="ID of the customer to retrieve")

    class ListCustomersInvoicesSchema(BaseModel):
        start_date: str | None = Field(
            None, description="Start date in format YYYY-MM-DD to filter invoices by"
        )
        customer_id: str | None = Field(
            None, description="Customer ID to filter invoices by"
        )

    class GetCustomerInvoiceSchema(BaseModel):
        invoice_id: str = Field(..., description="ID of the invoice to retrieve")

    async def list_customers() -> list[Any]:
        return await integration.list_customers()

    async def get_customer(customer_id: str) -> dict[str, Any]:
        return await integration.get_customer(customer_id)

    async def list_customer_invoices(
        start_date: str | None = None, customer_id: str | None = None
    ) -> list[Any]:
        return await integration.list_customer_invoices(
            start_date=start_date, customer_id=customer_id
        )

    async def get_customer_invoice(invoice_id: str) -> dict[str, Any]:
        return await integration.get_customer_invoice(invoice_id)

    return [
        StructuredTool(
            name="pennylane_list_customers",
            description="List customers from Pennylane.",
            coroutine=list_customers,
            args_schema=ListCustomersSchema,
        ),
        StructuredTool(
            name="pennylane_get_customer_details",
            description="Get details for a specific customer from Pennylane.",
            coroutine=get_customer,
            args_schema=GetCustomerDetailsSchema,
        ),
        StructuredTool(
            name="pennylane_list_customers_invoices",
            description="List customer invoices from Pennylane.",
            coroutine=list_customer_invoices,
            args_schema=ListCustomersInvoicesSchema,
        ),
        StructuredTool(
            name="pennylane_get_customer_invoice",
            description="Get a specific customer invoice from Pennylane.",
            coroutine=get_customer_invoice,
            args_schema=GetCustomerInvoiceSchema,
        ),
    ]
