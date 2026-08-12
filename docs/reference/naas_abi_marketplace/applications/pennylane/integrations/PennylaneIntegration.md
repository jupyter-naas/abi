# PennylaneIntegration

## What it is
- A Pennylane API integration client for retrieving accounting/finance data:
  - customers, customer invoices, invoice categories, categories, category groups, bank transactions
- Persists retrieved data as JSON files under a configured datastore path.
- Provides optional LangChain `StructuredTool` wrappers via `as_tools()`.

## Public API

### `PennylaneIntegrationConfiguration` (dataclass)
Configuration for the integration.
- `api_key: str` — Pennylane API key (used as Bearer token).
- `base_url: str` — Base API URL (default: `https://app.pennylane.com/api/external`).
- `datastore_path: str` — Output base directory for saved JSON (default from `ABIModule.get_instance().configuration.datastore_path`).

### `PennylaneIntegration` (class)
Integration client (inherits `naas_abi_core.integration.integration.Integration`).

- `__init__(configuration: PennylaneIntegrationConfiguration)`
  - Initializes request headers and storage utilities.

- `list_customers(sort: str = "-id", filters: list | None = None) -> list`
  - Lists customers (paginated).
  - Saves JSON to: `<datastore_path>/list_customers/<file>.json`.

- `get_customer(customer_id: str) -> dict`
  - Retrieves a customer by ID.
  - Cached for 1 day (FS cache).
  - Saves JSON to: `<datastore_path>/get_customer/<customer_id>/<customer_id>.json`.

- `list_customer_invoices(sort: str = "-date", filters: list | None = None, customer_id: str | None = None, start_date: str | None = None) -> list`
  - Lists customer invoices (paginated).
  - If `customer_id` and/or `start_date` are provided, corresponding filters are appended.
  - Saves JSON to: `<datastore_path>/list_customer_invoices/<file>.json`.

- `get_customer_invoice(invoice_id: str) -> dict`
  - Retrieves a customer invoice by ID.
  - Cached for 1 day (FS cache).
  - Saves JSON to: `<datastore_path>/get_customer_invoice/<invoice_id>/<invoice_id>.json`.

- `get_customer_invoice_categories(invoice_id: str) -> list`
  - Lists categories for a specific customer invoice (paginated).
  - Cached for 1 day (FS cache).
  - Saves JSON to: `<datastore_path>/get_customer_invoice_categories/<invoice_id>/<invoice_id>.json`.

- `list_categories(sort: str = "-id", filters: list | None = None) -> list`
  - Lists categories (paginated).
  - Saves JSON to: `<datastore_path>/list_categories/<file>.json`.

- `list_category_groups() -> list`
  - Lists category groups (paginated).
  - Saves JSON to: `<datastore_path>/list_category_groups/list_category_groups.json`.

- `list_bank_transactions(sort: str = "-id", filters: list | None = None) -> list`
  - Lists bank transactions (paginated).
  - Saves JSON to: `<datastore_path>/list_bank_transactions/<file>.json`.

### `as_tools(configuration: PennylaneIntegrationConfiguration) -> list`
Converts the integration into LangChain tools (`langchain_core.tools.StructuredTool`):
- `pennylane_list_customers`
- `pennylane_get_customer_details`
- `pennylane_list_customers_invoices`
- `pennylane_get_customer_invoice`

## Configuration/Dependencies
- **HTTP**: `requests` with headers:
  - `Authorization: Bearer <api_key>`
  - `Content-Type: application/json`
  - `Accept: application/json`
- **Caching**: `naas_abi_core.services.cache.CacheFactory` FS cache (subpath: `"pennylane"`); some methods cached with TTL = 1 day.
- **Storage**: `naas_abi_core.utils.StorageUtils.StorageUtils` writing JSON outputs under `datastore_path` using the application object storage engine from `ABIModule`.
- **Optional (for `as_tools`)**:
  - `langchain_core`
  - `pydantic`

## Usage

```python
from naas_abi_marketplace.applications.pennylane.integrations.PennylaneIntegration import (
    PennylaneIntegration,
    PennylaneIntegrationConfiguration,
)

cfg = PennylaneIntegrationConfiguration(api_key="YOUR_API_KEY")
client = PennylaneIntegration(cfg)

customers = client.list_customers()
print("customers:", len(customers))

customer = client.get_customer("123")
print("customer id:", customer.get("id"))

invoices = client.list_customer_invoices(customer_id="123", start_date="2024-01-01")
print("invoices:", len(invoices))

invoice = client.get_customer_invoice("456")
print("invoice id:", invoice.get("id"))
```

## Caveats
- `list_customer_invoices()` appends filters to the provided `filters` list (mutates it) when `customer_id` and/or `start_date` are set.
- Pagination assumes API responses contain `has_more`, `items`, and `next_cursor`; if the API response shape differs, `_get_all_items()` may not return complete results.
- HTTP errors are re-raised as `IntegrationConnectionError`.
