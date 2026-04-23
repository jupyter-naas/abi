# ExchangeratesapiIntegration

## What it is
- A small integration wrapper around the [exchangeratesapi.io](https://exchangeratesapi.io/) HTTP API.
- Provides:
  - Cached retrieval of available currency symbols.
  - Cached retrieval of exchange rates for a given date/base/symbol set.
- Includes a helper to expose the integration as LangChain `StructuredTool`s.

## Public API

### `ExchangeratesapiIntegrationConfiguration`
Dataclass configuration used to instantiate the integration.
- `api_key: str` (required): API key used as `access_key` query parameter.
- `base_url: str = "https://api.exchangeratesapi.io/v1"`: API base URL.

### `ExchangeratesapiIntegration`
Main integration class.

#### `__init__(configuration: ExchangeratesapiIntegrationConfiguration)`
- Stores configuration and prepares default request params (`{"access_key": api_key}`).

#### `list_symbols() -> Dict`
- Calls `GET /symbols`.
- Cached (filesystem cache via `CacheFactory.CacheFS_find_storage(subpath="exchangeratesapi")`).

#### `get_exchange_rates(date: str = "latest", base: str = "EUR", symbols: list[str] = []) -> Dict`
- Calls `GET /{date}` with query params:
  - `base=<base>`
  - `symbols=<comma-separated>` (only if `symbols` is non-empty)
- Cached with a key including `date`, `base`, and `symbols` (or `ALL` if none).

### `as_tools(configuration: ExchangeratesapiIntegrationConfiguration) -> list[langchain_core.tools.BaseTool]`
- Returns two LangChain `StructuredTool`s:
  - `exchangeratesapi_get_exchange_rates`
  - `exchangeratesapi_list_symbols`

## Configuration/Dependencies
- Requires:
  - `requests`
  - `naas_abi_core` (integration base classes, cache factory/port, `IntegrationConnectionError`)
  - `langchain_core` (only for `as_tools`)
  - `pydantic` (only for `as_tools` schemas)
- Authentication:
  - Uses query parameter `access_key=<api_key>` on every request.
- Caching:
  - Uses a filesystem-backed cache created with `CacheFactory.CacheFS_find_storage(subpath="exchangeratesapi")`.
  - Cached return type is JSON (`DataType.JSON`).

## Usage

### Direct integration usage
```python
from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    ExchangeratesapiIntegration,
    ExchangeratesapiIntegrationConfiguration,
)

cfg = ExchangeratesapiIntegrationConfiguration(api_key="YOUR_API_KEY")
client = ExchangeratesapiIntegration(cfg)

symbols = client.list_symbols()
rates = client.get_exchange_rates(date="latest", base="EUR", symbols=["USD", "GBP"])

print(symbols)
print(rates)
```

### As LangChain tools
```python
from naas_abi_marketplace.applications.exchangeratesapi.integrations.ExchangeratesapiIntegration import (
    as_tools,
    ExchangeratesapiIntegrationConfiguration,
)

tools = as_tools(ExchangeratesapiIntegrationConfiguration(api_key="YOUR_API_KEY"))

# Example direct invocation of the StructuredTool function (without an agent):
result = tools[0].func(date="latest", base="EUR", symbols=["USD"])
print(result)
```

## Caveats
- Network/request failures are raised as `IntegrationConnectionError`.
- `get_exchange_rates(..., symbols=[])` uses a mutable default list; pass your own list to avoid accidental shared mutations in long-running contexts.
- Cache keys for `symbols` depend on list order (e.g., `["USD","GBP"]` vs `["GBP","USD"]` produce different cache entries).
