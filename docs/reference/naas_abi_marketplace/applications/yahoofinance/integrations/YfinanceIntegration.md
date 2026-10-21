# YfinanceIntegration

## What it is
A Yahoo Finance integration built on top of `yfinance` (and `yahooquery.search`) that:
- Retrieves ticker info, historical prices, and selected financial data
- Retrieves sector and industry summaries
- Searches for tickers by company name
- Caches responses (filesystem cache) and persists JSON outputs under a configured datastore path

## Public API

### `YfinanceIntegrationConfiguration`
Dataclass extending `IntegrationConfiguration`.

- `datastore_path: str`
  - Base path where JSON outputs are saved.
  - Defaults to `ABIModule.get_instance().configuration.datastore_path`.

### `YfinanceIntegration`
Integration client (extends `Integration`).

- `get_ticker_info(symbol: str) -> dict`
  - Returns `yf.Ticker(symbol).info`.
  - Cache TTL: 1 hour.
  - Saved to: `tickers/{symbol}/{symbol}_info.json`.

- `get_ticker_history(symbol: str, period: str = "1mo") -> list[dict]`
  - Returns `yf.Ticker(symbol).history(period=period)` converted to a list of records.
  - Cache TTL: 15 minutes.
  - Saved to: `tickers/{symbol}/{symbol}_history_{period}.json`.

- `get_ticker_financials(symbol: str) -> dict`
  - Returns a dict with:
    - `quarterly_income_stmt`: from `ticker.quarterly_income_stmt` (as records)
    - `calendar`: from `ticker.calendar` converted to JSON-safe values (or `[]`)
    - `analyst_price_targets`: from `ticker.analyst_price_targets` (or `{}`)
  - Cache TTL: 6 hours.
  - Saved to: `tickers/{symbol}/{symbol}_financials.json`.

- `get_sector_info(sector_key: str) -> dict`
  - Uses `yf.Sector(sector_key)` and returns a summary dict including:
    - `key`, `name`, `symbol`
    - `ticker` info (if available)
    - `overview`, `top_companies`, `research_reports`, `top_etfs`, `top_mutual_funds`, `industries` (when available)
  - Cache TTL: 2 hours.
  - Saved to: `sectors/{sector_key}/{sector_key}_info.json`.

- `get_industry_info(industry_key: str) -> dict`
  - Uses `yf.Industry(industry_key)` and returns:
    - `sector_key`, `sector_name`
    - `top_performing_companies`, `top_growth_companies` (when available, as records)
  - Cache TTL: 2 hours.
  - Saved to: `industries/{industry_key}/{industry_key}_info.json`.

- `search_ticker(company_name: str) -> list[dict]`
  - Uses `yahooquery.search(company_name)` and returns `results["quotes"]` (or `[]`).
  - Cache TTL: 1 hour.
  - Saved to: `search/{company_name}/{company_name}_search.json` (spaces replaced with `_`).

**Errors**
- Each public method wraps failures as `IntegrationConnectionError`.
- Save failures do **not** fail the call; they are logged and the data is still returned.

### `as_tools(configuration: YfinanceIntegrationConfiguration) -> list`
Creates LangChain `StructuredTool` wrappers around the integration methods:

- `yfinance_get_ticker_info`
- `yfinance_get_ticker_history`
- `yfinance_get_ticker_financials`
- `yfinance_get_sector_info`
- `yfinance_get_industry_info`
- `yfinance_search_ticker`

## Configuration/Dependencies

- External packages:
  - `yfinance`
  - `yahooquery`
  - `pandas`
- Naas ABI dependencies:
  - `naas_abi_core` (`Integration`, caching, `StorageUtils`, `logger`)
  - `ABIModule` (provides default `datastore_path` and object storage service)
- Caching:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="yahoofinance")`
  - Cache type: `DataType.JSON`
  - TTL varies per method (see Public API)

## Usage

### Basic usage
```python
from naas_abi_marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
    YfinanceIntegration,
    YfinanceIntegrationConfiguration,
)

config = YfinanceIntegrationConfiguration(datastore_path="datastore/yahoofinance")
client = YfinanceIntegration(config)

info = client.get_ticker_info("AAPL")
history = client.get_ticker_history("AAPL", period="1mo")
financials = client.get_ticker_financials("AAPL")
matches = client.search_ticker("Apple")
```

### As LangChain tools
```python
from naas_abi_marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
    as_tools,
    YfinanceIntegrationConfiguration,
)

tools = as_tools(YfinanceIntegrationConfiguration(datastore_path="datastore/yahoofinance"))
```

## Caveats
- Returned data depends on Yahoo/yfinance availability; keys/fields may be missing.
- DataFrame conversion behavior:
  - Empty/`None` results become `[]`.
  - `DatetimeIndex` is stringified (`%Y-%m-%dT%H:%M:%S%z`).
  - `NaN` values become `0` in DataFrame-to-record conversion (`_result_df_to_dict`).
  - In calendar/other JSON conversion, `NaN` becomes `None` and datetime-like objects become ISO strings.
- Persistence is best-effort: storage errors are logged but do not stop the request.
