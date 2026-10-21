# AgicapIntegration

## What it is
- An integration client for Agicap APIs:
  - Public OpenAPI endpoint to list companies (API token).
  - App endpoints to fetch accounts, transactions, balances, and debts (bearer token).
- Includes a helper to expose methods as LangChain `StructuredTool`s.

## Public API

### `AgicapIntegrationConfiguration`
Dataclass configuration for the integration.

- Fields:
  - `username: str`, `password: str`: used to fetch a bearer token when `bearer_token` is empty.
  - `api_token: str`: used for `list_companies()` (public OpenAPI).
  - `bearer_token: str`: used for app/debt endpoints; auto-fetched if empty.
  - `client_id: str`: present but not used by token retrieval logic.
  - `client_secret: str`: used to fetch bearer token.
  - `base_url: str = "https://app.agicap.com/api"`: base URL for some endpoints.

### `AgicapIntegration`
Client providing HTTP calls to Agicap.

- `__init__(configuration: AgicapIntegrationConfiguration)`
  - Stores configuration.
  - If `bearer_token` is falsy, calls `_get_bearer_token()` and stores it back into the configuration.

- `list_companies() -> dict`
  - `GET https://openapi.agicap.com/api/companies`
  - Auth: `Authorization: Bearer <api_token>`
  - Wraps `requests` errors as `IntegrationConnectionError`.

- `get_company_accounts(company_id: str) -> dict`
  - `GET https://app.agicap.com/api/banque/GetAll`
  - Headers include `Authorization: Bearer <bearer_token>` and `Entrepriseid: <company_id>`
  - Returns `response.json().get("Result")`
  - Wraps `requests` errors as `IntegrationConnectionError`.

- `get_transactions(company_id: str, account_id: str, limit: int = 100) -> list[dict]`
  - `POST {base_url}/paidtransaction/GetByFilters`
  - Paginates using `pagination.skip`/`pagination.take` in the payload; appends results until:
    - the API returns an empty page, or
    - collected items reach `limit`.
  - Flattens nested dict fields in each transaction (keys joined with `_`).
  - Logs progress via `naas_abi_core.logger`.

- `get_balance(company_id: str, account_id: str | None = None) -> dict`
  - If `account_id` provided:
    - `GET https://app.agicap.com/api/forecasting/v2/bank/{account_id}/cash-balances?frequency=2`
  - Else:
    - `GET https://app.agicap.com/api/forecasting/v2/bank/cash-balances?frequency=2&`
  - Header includes `EntrepriseId: <company_id>`

- `get_debts(company_id: str) -> dict`
  - `GET https://debt-management.agicap.com/v3/entities/{company_id}/debts`

### `as_tools(configuration: AgicapIntegrationConfiguration) -> list`
- Returns a list of LangChain `StructuredTool`s backed by an `AgicapIntegration` instance:
  - `agicap_list_companies`
  - `agicap_get_company_accounts(company_id)`
  - `agicap_get_transactions(company_id, account_id, limit=10)`
  - `agicap_get_balance(company_id, account_id=None)`
  - `agicap_get_debts(company_id)`

## Configuration/Dependencies
- Runtime dependencies:
  - `requests`
  - `naas_abi_core` (`logger`, `Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`)
- Optional (only required for `as_tools`):
  - `langchain_core.tools.StructuredTool`
  - `pydantic`
- Authentication:
  - `api_token` is required for `list_companies()`.
  - `bearer_token` is required for other endpoints; if not provided, it is fetched using `username`, `password`, and `client_secret`.

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
    bearer_token="",  # leave empty to auto-fetch
    client_id="unused",
    client_secret="your-client-secret",
)

agicap = AgicapIntegration(cfg)

companies = agicap.list_companies()
print(companies)

# If you have IDs:
# accounts = agicap.get_company_accounts(company_id="...")
# tx = agicap.get_transactions(company_id="...", account_id="...", limit=50)
# balance = agicap.get_balance(company_id="...", account_id=None)
# debts = agicap.get_debts(company_id="...")
```

## Caveats
- Token retrieval uses a hard-coded OAuth `client_id` value (`"legacy-token"`) and does not use `configuration.client_id`.
- `get_transactions()` updates a local `skip` counter but does not update `payload["pagination"]["skip"]` after the first request; it also increments `skip` by `100` each loop.
- Only `list_companies()` and `get_company_accounts()` wrap network failures into `IntegrationConnectionError`; other methods rely on `requests.raise_for_status()` and will propagate `requests` exceptions.
