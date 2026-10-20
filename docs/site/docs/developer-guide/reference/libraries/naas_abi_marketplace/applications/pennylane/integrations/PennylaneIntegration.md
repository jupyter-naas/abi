# PennylaneIntegration

## What it is
- A Pennylane API client integration for fetching accounting/finance data (customers, invoices, categories, transactions).
- Persists API responses as JSON files under a configured datastore path.
- Provides optional LangChain `StructuredTool` wrappers via `as_tools()`.

## Public API

### `PennylaneIntegrationConfiguration`
Configuration dataclass for the integration.
- **Fields**
  - `api_key: str` — Pennylane API key (Bearer token).
  - `base_url: str` — Base API URL (default: `"https://app.pennylane.com/api/external"`).
  - `datastore_path: str` — Base folder used to save JSON outputs (default comes from `ABIModule.get_instance().configuration.datastore_path`).

### `PennylaneIntegration`
Integration client (inherits `Integration`).
- **Constructor**
  - `__init__(configuration: PennylaneIntegrationConfiguration)` — initializes headers and storage.
- **Methods**
  - `list_customers(sort: str = "-id", filters: list = []) -> list`
    - Lists customers; supports optional API filtering via `filters`.
    - Saves to: `<datastore_path>/list_customers/<file>.json`.
  - `get_customer(customer_id: str) -> Dict`
    - Fetches a single customer by id.
    - Cached (FS cache) for 1 day.
    - Saves to: `<datastore_path>/get_customer/<customer_id>/<customer_id>.json`.
  - `list_customer_invoices(sort: str = "-date", filters: list = [], customer_id: Optional[str] = None, start_date: Optional[str] = None) -> list`
    - Lists customer invoices; can append filters for `customer_id` and/or `start_date`.
    - Saves to: `<datastore_path>/list_customer_invoices/<file>.json`.
  - `get_customer_invoice(invoice_id: str) -> Dict`
    - Fetches a single invoice by id.
    - Cached (FS cache) for 1 day.
    - Saves to: `<datastore_path>/get_customer_invoice/<invoice_id>/<invoice_id>.json`.
  - `get_customer_invoice_categories(invoice_id: str) -> list`
    - Lists categories for a specific customer invoice.
    - Cached (FS cache) for 1 day.
    - Saves to: `<datastore_path>/get_customer_invoice_categories/<invoice_id>/<invoice_id>.json`.
  - `list_categories(sort: str = "-id", filters: list = []) -> list`
    - Lists categories; supports optional API filtering via `filters`.
    - Saves to: `<datastore_path>/list_categories/<file>.json`.
  - `list_category_groups() -> list`
    - Lists category groups.
    - Saves to: `<datastore_path>/list_category_groups/list_category_groups.json`.
  - `list_bank_transactions(sort: str = "-id", filters: list = []) -> list`
    - Lists bank transactions; supports optional API filtering via `filters`.
    - Saves to: `<datastore_path>/list_bank_transactions/<file>.json`.

### `as_tools(configuration: PennylaneIntegrationConfiguration) -> list`
- Returns a list of LangChain `StructuredTool` objects backed by an internal `PennylaneIntegration` instance:
  - `pennylane_list_customers`
  - `pennylane_get_customer_details`
  - `pennylane_list_customers_invoices`
  - `pennylane_get_customer_invoice`

## Configuration/Dependencies
- **HTTP**: Uses `requests` and Bearer authentication header: `Authorization: Bearer <api_key>`.
- **Caching**: Uses `naas_abi_core.services.cache` with an FS-backed cache (`CacheFactory.CacheFS_find_storage(subpath="pennylane")`); some getters are cached for 1 day.
- **Storage**: Writes JSON files via `naas_abi_core.utils.StorageUtils.StorageUtils` to `datastore_path` (provided by `ABIModule` by default).
- **Optional (for `as_tools`)**:
  - `langchain_core.tools.StructuredTool`
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
print(len(customers))

customer = client.get_customer(customer_id="123")
print(customer.get("id"))

invoices = client.list_customer_invoices(customer_id="123", start_date="2024-01-01")
print(len(invoices))

invoice = client.get_customer_invoice(invoice_id="456")
print(invoice.get("id"))
```

## Caveats
- Mutable default arguments are used (`filters: list = []`, `params: Dict = {}`, `json: Dict = {}`); callers should avoid mutating passed-in objects and prefer providing fresh lists/dicts.
- `list_customer_invoices()` appends filter entries to the provided `filters` list (in-place) when `customer_id` and/or `start_date` are set.
- API pagination relies on response keys: `has_more`, `items`, `next_cursor`. If the API format differs, pagination may not work as expected.
- Errors from `requests` are wrapped and raised as `IntegrationConnectionError`.
