# YfinanceIntegration

## What it is
A Yahoo Finance integration client built on `yfinance` (and `yahooquery.search`) that:
- Fetches ticker info, price history, and selected financial data
- Fetches sector and industry summaries
- Searches tickers by company name
- Caches results (filesystem cache) and persists JSON outputs to an object storage-backed datastore path

## Public API

### Configuration
- `YfinanceIntegrationConfiguration(IntegrationConfiguration)`
  - `datastore_path: str` — base path used to store saved JSON outputs (defaults to `ABIModule.get_instance().configuration.datastore_path`).

### Client
- `class YfinanceIntegration(Integration)`
  - `get_ticker_info(symbol: str) -> Dict`
    - Returns `yf.Ticker(symbol).info`.
    - Cached for 1 hour; saved to `tickers/{symbol}/{symbol}_info.json`.
  - `get_ticker_history(symbol: str, period: str = "1mo") -> List[Dict]`
    - Returns historical OHLCV from `yf.Ticker(symbol).history(period=period)` converted to a list of records.
    - Cached for 15 minutes; saved to `tickers/{symbol}/{symbol}_history_{period}.json`.
  - `get_ticker_financials(symbol: str) -> Dict`
    - Returns a dict with:
      - `quarterly_income_stmt` (from `ticker.quarterly_income_stmt`, converted to records)
      - `calendar` (from `ticker.calendar`, converted to JSON-serializable structures when present)
      - `analyst_price_targets` (from `ticker.analyst_price_targets` when present)
    - Cached for 6 hours; saved to `tickers/{symbol}/{symbol}_financials.json`.
  - `get_sector_info(sector_key: str) -> Dict`
    - Returns sector details from `yf.Sector(sector_key)` including overview, top companies, ETFs, mutual funds, industries (when available).
    - Cached for 2 hours; saved to `sectors/{sector_key}/{sector_key}_info.json`.
  - `get_industry_info(industry_key: str) -> Dict`
    - Returns industry details from `yf.Industry(industry_key)` including sector key/name and top performing/growth companies (when available).
    - Cached for 2 hours; saved to `industries/{industry_key}/{industry_key}_info.json`.
  - `search_ticker(company_name: str) -> List[Dict]`
    - Uses `yahooquery.search(company_name)` and returns the `"quotes"` list (or `[]`).
    - Cached for 1 hour; saved to `search/{company}/..._search.json`.

Errors:
- Public methods wrap failures in `IntegrationConnectionError`.

### LangChain tools
- `as_tools(configuration: YfinanceIntegrationConfiguration) -> list`
  - Returns a list of `langchain_core.tools.StructuredTool` wrapping the integration methods:
    - `yfinance_get_ticker_info`
    - `yfinance_get_ticker_history`
    - `yfinance_get_ticker_financials`
    - `yfinance_get_sector_info`
    - `yfinance_get_industry_info`
    - `yfinance_search_ticker`

## Configuration/Dependencies
- Python packages:
  - `yfinance`
  - `yahooquery`
  - `pandas`
- Naas ABI components:
  - `naas_abi_core` (`Integration`, cache system, `StorageUtils`, `logger`)
  - `naas_abi_marketplace.applications.yahoofinance.ABIModule` (provides default `datastore_path` and object storage service)
- Caching:
  - Uses `CacheFactory.CacheFS_find_storage(subpath="yahoofinance")`
  - Cache entries store JSON and respect per-method TTLs.

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
results = client.search_ticker("Apple")
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
- Data is returned “as provided” by `yfinance`/Yahoo; fields may be missing or vary by symbol/asset.
- DataFrame conversions:
  - Empty/`None` frames become `[]`.
  - Datetime indexes are stringified; `NaN` is converted to `0` in historical/statement record conversion.
- Persistence failures do not stop the call: `_save_data` logs an error and returns the original data.
