# ExchangeratesapiIntegration

## What it is
- A small integration wrapper around the Exchangeratesapi HTTP API (`https://api.exchangeratesapi.io/v1`).
- Provides:
  - Listing available currency symbols.
  - Fetching exchange rates for a given date/base/symbol set.
  - Filesystem-backed caching for both calls.
  - Optional exposure as LangChain `StructuredTool`s.

## Public API

### `ExchangeratesapiIntegrationConfiguration`
Dataclass used to configure the integration.
- `api_key: str` — API key passed as `access_key` query parameter.
- `base_url: str = "https://api.exchangeratesapi.io/v1"` — API base URL.

### `ExchangeratesapiIntegration`
Main integration class.

- `__init__(configuration: ExchangeratesapiIntegrationConfiguration)`
  - Stores configuration and prepares default request params (`{"access_key": api_key}`).

- `list_symbols() -> dict`
  - Calls `GET /symbols`.
  - Cached under the key `"list_symbols"` (JSON).

- `get_exchange_rates(date: str = "latest", base: str = "EUR", symbols: list[str] | None = None) -> dict`
  - Calls `GET /{date}` with query params:
    - `base=<base>`
    - `symbols=<comma-separated>` (only when `symbols` is non-empty)
  - Cached under key:
    - `get_exchange_rates_{date}_{base}_{ALL|<comma-separated symbols>}` (JSON)

### `as_tools(configuration: ExchangeratesapiIntegrationConfiguration) -> list[langchain_core.tools.BaseTool]`
- Returns two LangChain `StructuredTool`s backed by a single `ExchangeratesapiIntegration` instance:
  - `exchangeratesapi_get_exchange_rates`
  - `exchangeratesapi_list_symbols`

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core` (`Integration`, `IntegrationConfiguration`, `IntegrationConnectionError`, `CacheFactory`, `DataType`)
  - `langchain_core.tools` (`BaseTool`, `StructuredTool`) for `as_tools`
  - `pydantic` for tool argument schemas
- Authentication:
  - Uses query parameter `access_key=<api_key>` on every request.
- Caching:
  - Uses filesystem cache from `CacheFactory.CacheFS_find_storage(subpath="exchangeratesapi")`.
  - Cached data type: `DataType.JSON`.

## Usage

### Direct integration usage
```python
from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    ExchangeratesapiIntegration,
    ExchangeratesapiIntegrationConfiguration,
)

cfg = ExchangeratesapiIntegrationConfiguration(api_key="YOUR_API_KEY")
client = ExchangeratesapiIntegration(cfg)

print(client.list_symbols())
print(client.get_exchange_rates(date="latest", base="EUR", symbols=["USD", "GBP"]))
```

### As LangChain tools
```python
from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    as_tools,
    ExchangeratesapiIntegrationConfiguration,
)

tools = as_tools(ExchangeratesapiIntegrationConfiguration(api_key="YOUR_API_KEY"))

# Invoke the tool function directly
result = tools[0].func(date="latest", base="EUR", symbols=["USD"])
print(result)
```

## Caveats
- HTTP failures (including non-2xx responses) raise `IntegrationConnectionError`.
- Cache keys for `symbols` depend on list order (`["USD","GBP"]` vs `["GBP","USD"]` create different entries).
- `get_exchange_rates(..., symbols=None)` is treated as “all symbols” (no `symbols` query parameter is sent).
