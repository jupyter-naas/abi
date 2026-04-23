# SecGovIntegration

## What it is
- A small integration that fetches public U.S. SEC (EDGAR) JSON resources over HTTP.
- Supports optional persistence of fetched JSON to an object storage backend.
- Uses a filesystem-backed cache (TTL: 7 days) for its main fetch methods.

## Public API

### `SecGovIntegrationConfiguration`
Dataclass configuration for the integration.
- `object_storage: ObjectStorageService` — object storage used to persist downloaded JSON when `save_result=True`.
- `user_agent: str` — required User-Agent header value for SEC requests.
- `datastore_path: str = "sec_gov"` — object storage prefix for saved artifacts.

### `SecGovIntegration`
Integration client.

#### `__init__(configuration: SecGovIntegrationConfiguration)`
- Initializes the integration and storage helper.

#### `make_request(url: str, *, method: str = "GET", headers: dict[str, str] | None = None, timeout: int = 120, **kwargs) -> requests.Response`
- Performs an HTTP request using `requests.request`.
- Adds default headers:
  - `User-Agent` from configuration
  - `Accept: application/json`
- Raises `IntegrationConnectionError` on request errors (including non-2xx responses).

#### `get_company_tickers(save_result: bool = False) -> dict[str, Any]`
- Fetches `https://www.sec.gov/files/company_tickers.json`.
- Optionally saves JSON to: `{datastore_path}/files/company_tickers/company_tickers.json`.
- Cached for 7 days.

#### `get_company_tickers_exchange(save_result: bool = False) -> dict[str, Any]`
- Fetches `https://www.sec.gov/files/company_tickers_exchange.json`.
- Optionally saves JSON to: `{datastore_path}/files/company_tickers_exchange/company_tickers_exchange.json`.
- Cached for 7 days.

#### `get_company_tickers_mf(save_result: bool = False) -> dict[str, Any]`
- Fetches `https://www.sec.gov/files/company_tickers_mf.json`.
- Optionally saves JSON to: `{datastore_path}/files/company_tickers_mf/company_tickers_mf.json`.
- Cached for 7 days.

#### `get_submissions(cik: str | int, save_result: bool = False) -> dict[str, Any]`
- Fetches `https://data.sec.gov/submissions/CIK{cik_10}.json` where `cik_10` is normalized to 10 digits.
- Optionally saves JSON to: `{datastore_path}/submissions/CIK{cik_10}.json`.
- Cached for 7 days.

#### `SecGovIntegration._normalize_cik(cik: str | int) -> str` (static)
- Normalizes a CIK by:
  - stripping whitespace,
  - removing a leading `CIK` prefix if present,
  - keeping only digits,
  - zero-padding to 10 digits.

### `as_tools(configuration: SecGovIntegrationConfiguration) -> list[BaseTool]`
- Returns an empty list (`[]`).

## Configuration/Dependencies
- **HTTP**: `requests`
- **SEC requirements**: a descriptive `user_agent` must be provided (used in all requests).
- **Caching**: `CacheFactory.CacheFS_find_storage(subpath="sec_gov")` with TTL of 7 days for fetch methods.
- **Persistence** (optional): `ObjectStorageService` used via `StorageUtils.save_json(...)` when `save_result=True`.

## Usage
```python
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_marketplace.applications.sec_gov.integrations.SecGovIntegration import (
    SecGovIntegration,
    SecGovIntegrationConfiguration,
)

# Provide a concrete ObjectStorageService implementation from your environment.
object_storage = ObjectStorageService(...)  # depends on your Naas ABI setup

cfg = SecGovIntegrationConfiguration(
    object_storage=object_storage,
    user_agent="YourCompany YourApp contact@yourcompany.com",
)

sec = SecGovIntegration(cfg)

tickers = sec.get_company_tickers()
submissions = sec.get_submissions("CIK0000320193", save_result=True)  # Apple example CIK
```

## Caveats
- Non-2xx HTTP responses raise `IntegrationConnectionError` (wrapping the underlying `requests` exception).
- `as_tools()` currently exposes no LangChain tools (always returns `[]`).
- Caching may return stale data for up to 7 days unless the cache is cleared externally.
