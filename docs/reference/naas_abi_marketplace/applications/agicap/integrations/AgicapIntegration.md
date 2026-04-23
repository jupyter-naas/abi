# AgicapIntegration

## What it is
- A small integration client to call several Agicap API endpoints:
  - Public OpenAPI companies listing (API token).
  - App API endpoints for accounts, transactions, balances, and debts (Bearer token).
- Includes a helper to expose these methods as LangChain `StructuredTool`s.

## Public API

### `AgicapIntegrationConfiguration`
Dataclass configuration for `AgicapIntegration`.

- Fields:
  - `username: str` / `password: str`: used to fetch a bearer token when `bearer_token` is empty.
  - `api_token: str`: used for the public OpenAPI companies endpoint.
  - `bearer_token: str`: used for app/debt endpoints; auto-fetched if empty.
  - `client_id: str`: present in config but **not used** in current code.
  - `client_secret: str`: used to fetch bearer token.
  - `base_url: str = "https://app.agicap.com/api"`: base URL for some endpoints.

### `AgicapIntegration`
Integration client.

- `__init__(configuration: AgicapIntegrationConfiguration)`
  - Initializes the integration.
  - If `configuration.bearer_token` is falsy, fetches one via `_get_bearer_token()`.

- `list_companies() -> Dict`
  - Calls `https://openapi.agicap.com/api/companies` with `Authorization: Bearer <api_token>`.
  - Wraps request errors into `IntegrationConnectionError`.

- `get_company_accounts(company_id: str) -> Dict`
  - Calls `https://app.agicap.com/api/banque/GetAll` with `Authorization: Bearer <bearer_token>` and `Entrepriseid: <company_id>`.
  - Returns `response.json().get("Result")`.
  - Wraps request errors into `IntegrationConnectionError`.

- `get_transactions(company_id: str, account_id: str, limit: int = 100) -> List[Dict]`
  - Calls `POST {base_url}/paidtransaction/GetByFilters` with pagination (`skip`/`take`), accumulating results until:
    - the API returns an empty page, or
    - collected items reach `limit`.
  - Flattens each transaction dict (nested dict keys joined with `_`) before returning.

- `get_balance(company_id: str, account_id: Optional[str] = None) -> Dict`
  - Calls forecasting cash-balances endpoint.
  - If `account_id` is provided: per-account URL.
  - Else: consolidated URL.

- `get_debts(company_id: str) -> Dict`
  - Calls `https://debt-management.agicap.com/v3/entities/{company_id}/debts`.

### `as_tools(configuration: AgicapIntegrationConfiguration) -> list`
- Returns a list of LangChain `StructuredTool` instances:
  - `agicap_list_companies`
  - `agicap_get_company_accounts(company_id)`
  - `agicap_get_transactions(company_id, account_id, limit=10)`
  - `agicap_get_balance(company_id, account_id=None)`
  - `agicap_get_debts(company_id)`

## Configuration/Dependencies
- Python packages used:
  - `requests`
  - `naas_abi_core` (for `logger` and base `Integration` types/exceptions)
- Optional (only needed for `as_tools`):
  - `langchain_core`
  - `pydantic`
- Authentication inputs:
  - `api_token` is required for `list_companies()`.
  - `bearer_token` is required for most other methods; if not provided, it is fetched using `username`, `password`, and `client_secret`.

## Usage

```python
from naas_abi_marketplace.applications.agicap.integrations.AgicapIntegration import (
    AgicapIntegration,
    AgicapIntegrationConfiguration,
)

cfg = AgicapIntegrationConfiguration(
    username="you@example.com",
    password="your-password",
    api_token="your-openapi-token",
    bearer_token="",          # leave empty to auto-fetch
    client_id="unused",
    client_secret="your-client-secret",
)

client = AgicapIntegration(cfg)

companies = client.list_companies()
print(companies)

# Example: fetch accounts/transactions if you have a company_id/account_id
# accounts = client.get_company_accounts(company_id="...")
# tx = client.get_transactions(company_id="...", account_id="...", limit=50)
# balance = client.get_balance(company_id="...", account_id=None)
# debts = client.get_debts(company_id="...")
```

## Caveats
- `client_id` is defined in configuration but not used in token retrieval (the request uses a hard-coded `"legacy-token"` client_id).
- `get_transactions()` increments `skip` by 100 regardless of the `take` size; the request payload’s `pagination.skip` is not updated after the first request (it remains the initial value in the payload).
- Only `list_companies()` and `get_company_accounts()` wrap network errors as `IntegrationConnectionError`; other methods let `requests.raise_for_status()` exceptions propagate.
