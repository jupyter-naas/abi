"""Yahoo Finance (``yfinance``, ``yahooquery``), on ``naas_abi_sdk`` only.

Port of ``naas_abi_marketplace.applications.yahoofinance.integrations``: same
data and tool names. Both libraries block, so each call runs in a worker thread
(``asyncio.to_thread``) and never stalls the module's event loop. Results are
archived to object storage under ``datastore_path`` when a storage is given.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from naas_abi_apps.common.storage import ObjectStorage, archive_json
from naas_abi_sdk.integration import (
    Integration,
    IntegrationConfiguration,
    IntegrationConnectionError,
)

logger = logging.getLogger(__name__)


def _yfinance() -> Any:
    import yfinance  # type: ignore[import-untyped]

    return yfinance


def _yahooquery_search(query: str) -> Any:
    from yahooquery import search  # type: ignore[import-untyped]

    return search(query)


@dataclass
class YfinanceIntegrationConfiguration(IntegrationConfiguration):
    """datastore_path / storage: where results are archived. yfinance /
    search: the libraries (tests pass fakes)."""

    datastore_path: str = "yahoofinance"
    storage: ObjectStorage | None = None
    yfinance: Callable[[], Any] = field(default=_yfinance, repr=False)
    search: Callable[[str], Any] = field(default=_yahooquery_search, repr=False)


def frame_to_records(result: Any) -> list[dict[str, Any]]:
    """A DataFrame as JSON records: index in ``key``, NaN as 0, snake_case columns."""
    import pandas as pd

    if result is None or result.empty:
        return []
    df = pd.DataFrame(result)
    if isinstance(df.index, pd.DatetimeIndex):
        df.index = df.index.strftime("%Y-%m-%dT%H:%M:%S%z")
    df.insert(0, "key", df.index)
    df = df.fillna(0)
    df.columns = [
        column.isoformat()
        if isinstance(column, pd.Timestamp)
        else str(column).strip().replace(" ", "_").lower()
        for column in df.columns
    ]
    return df.to_dict(orient="records")


def to_json(value: Any) -> Any:
    """Timestamps, dates and NaN in dicts and lists as JSON values."""
    import pandas as pd

    if isinstance(value, dict):
        return {key: to_json(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [to_json(item) for item in value]
    if hasattr(value, "isoformat"):
        return value.isoformat()
    try:
        if pd.isna(value):
            return None
    except (TypeError, ValueError):
        pass
    return value


class YfinanceIntegration(Integration):
    """Tickers (info, history, financials), sectors, industries, ticker search."""

    def __init__(self, configuration: YfinanceIntegrationConfiguration):
        super().__init__(configuration)
        self.configuration = configuration

    async def _run(
        self, what: str, fn: Callable[[], Any], folder: str, file_name: str
    ) -> Any:
        try:
            data = await asyncio.to_thread(fn)
        except Exception as exc:  # the libraries raise anything
            raise IntegrationConnectionError(f"Failed to get {what}: {exc!s}") from exc
        try:
            await archive_json(
                self.configuration.storage,
                f"{self.configuration.datastore_path}/{folder}",
                file_name,
                data,
            )
        except Exception as exc:  # noqa: BLE001 - archiving never fails the call
            logger.error("Error saving %s/%s: %s", folder, file_name, exc)
        return data

    async def get_ticker_info(self, symbol: str) -> dict[str, Any]:
        """Company details and financial metrics of a ticker (e.g. "AAPL", "ALO.PA")."""

        def info() -> Any:
            return to_json(self.configuration.yfinance().Ticker(symbol).info)

        return await self._run(
            f"ticker info for {symbol}",
            info,
            f"tickers/{symbol}",
            f"{symbol}_info.json",
        )

    async def get_ticker_history(
        self, symbol: str, period: str = "1mo"
    ) -> list[dict[str, Any]]:
        """OHLCV history over ``period`` (1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max)."""

        def history() -> Any:
            return frame_to_records(
                self.configuration.yfinance().Ticker(symbol).history(period=period)
            )

        return await self._run(
            f"ticker history for {symbol}",
            history,
            f"tickers/{symbol}",
            f"{symbol}_history_{period}.json",
        )

    async def get_ticker_financials(self, symbol: str) -> dict[str, Any]:
        """Quarterly income statement, calendar and analyst price targets."""

        def financials() -> Any:
            ticker = self.configuration.yfinance().Ticker(symbol)
            calendar = getattr(ticker, "calendar", None)
            return {
                "quarterly_income_stmt": frame_to_records(ticker.quarterly_income_stmt),
                "calendar": to_json(
                    calendar if isinstance(calendar, list) else [calendar]
                )
                if calendar is not None
                else [],
                "analyst_price_targets": to_json(
                    getattr(ticker, "analyst_price_targets", {})
                ),
            }

        return await self._run(
            f"ticker financials for {symbol}",
            financials,
            f"tickers/{symbol}",
            f"{symbol}_financials.json",
        )

    async def get_sector_info(self, sector_key: str) -> dict[str, Any]:
        """A sector ("technology", "healthcare", ...): top companies, ETFs, funds, industries."""

        def sector_info() -> Any:
            sector = self.configuration.yfinance().Sector(sector_key)
            ticker = getattr(sector, "ticker", None)
            return to_json(
                {
                    "key": sector.key,
                    "name": sector.name,
                    "symbol": sector.symbol,
                    "ticker": getattr(ticker, "info", {}) if ticker is not None else {},
                    "overview": getattr(sector, "overview", {}),
                    "top_companies": frame_to_records(
                        getattr(sector, "top_companies", None)
                    ),
                    "research_reports": getattr(sector, "research_reports", []),
                    "top_etfs": getattr(sector, "top_etfs", []),
                    "top_mutual_funds": getattr(sector, "top_mutual_funds", []),
                    "industries": frame_to_records(getattr(sector, "industries", None)),
                }
            )

        return await self._run(
            f"sector info for {sector_key}",
            sector_info,
            f"sectors/{sector_key}",
            f"{sector_key}_info.json",
        )

    async def get_industry_info(self, industry_key: str) -> dict[str, Any]:
        """An industry ("software", "banks", ...): sector, top performing and growth companies."""

        def industry_info() -> Any:
            industry = self.configuration.yfinance().Industry(industry_key)
            return {
                "sector_key": getattr(industry, "sector_key", ""),
                "sector_name": getattr(industry, "sector_name", ""),
                "top_performing_companies": frame_to_records(
                    getattr(industry, "top_performing_companies", None)
                ),
                "top_growth_companies": frame_to_records(
                    getattr(industry, "top_growth_companies", None)
                ),
            }

        return await self._run(
            f"industry info for {industry_key}",
            industry_info,
            f"industries/{industry_key}",
            f"{industry_key}_info.json",
        )

    async def search_ticker(self, company_name: str) -> list[dict[str, Any]]:
        """Ticker symbols matching a company name."""
        slug = company_name.replace(" ", "_")

        def quotes() -> Any:
            results = self.configuration.search(company_name)
            return results.get("quotes", []) if isinstance(results, dict) else []

        return await self._run(
            f"search results for {company_name}",
            quotes,
            f"search/{slug}",
            f"{slug}_search.json",
        )


def as_tools(configuration: YfinanceIntegrationConfiguration) -> list[Any]:
    """LangChain tools over the integration."""
    from langchain_core.tools import StructuredTool
    from pydantic import BaseModel, Field

    integration = YfinanceIntegration(configuration)

    class TickerSymbolSchema(BaseModel):
        symbol: str = Field(
            ..., description="Stock ticker symbol (e.g., 'AAPL', 'ALO.PA', 'TSLA')"
        )

    class TickerHistorySchema(BaseModel):
        symbol: str = Field(..., description="Stock ticker symbol")
        period: str = Field(
            "1mo",
            description="Time period: 1d, 5d, 1mo, 3mo, 6mo, 1y, 2y, 5y, 10y, ytd, max",
        )

    class SectorKeySchema(BaseModel):
        sector_key: str = Field(
            ...,
            description="Sector identifier (e.g., 'technology', 'healthcare', 'financials', 'industrials')",
        )

    class IndustryKeySchema(BaseModel):
        industry_key: str = Field(
            ...,
            description="Industry identifier (e.g., 'software', 'biotech', 'banks', 'railroads')",
        )

    class CompanySearchSchema(BaseModel):
        company_name: str = Field(
            ..., description="Company name to search for ticker symbol"
        )

    async def get_ticker_info(symbol: str) -> Any:
        return await integration.get_ticker_info(symbol)

    async def get_ticker_history(symbol: str, period: str = "1mo") -> Any:
        return await integration.get_ticker_history(symbol, period)

    async def get_ticker_financials(symbol: str) -> Any:
        return await integration.get_ticker_financials(symbol)

    async def get_sector_info(sector_key: str) -> Any:
        return await integration.get_sector_info(sector_key)

    async def get_industry_info(industry_key: str) -> Any:
        return await integration.get_industry_info(industry_key)

    async def search_ticker(company_name: str) -> Any:
        return await integration.search_ticker(company_name)

    return [
        StructuredTool(
            name="yfinance_get_ticker_info",
            description="Get basic information for a stock ticker including company details and financial metrics",
            coroutine=get_ticker_info,
            args_schema=TickerSymbolSchema,
        ),
        StructuredTool(
            name="yfinance_get_ticker_history",
            description="Get historical price data for a stock ticker with OHLCV information",
            coroutine=get_ticker_history,
            args_schema=TickerHistorySchema,
        ),
        StructuredTool(
            name="yfinance_get_ticker_financials",
            description="Get financial statements for a stock ticker including income statement, calendar, and analyst targets",
            coroutine=get_ticker_financials,
            args_schema=TickerSymbolSchema,
        ),
        StructuredTool(
            name="yfinance_get_sector_info",
            description="Get detailed information about a market sector including top companies, ETFs, and industries",
            coroutine=get_sector_info,
            args_schema=SectorKeySchema,
        ),
        StructuredTool(
            name="yfinance_get_industry_info",
            description="Get detailed information about a market industry including top performing and growth companies",
            coroutine=get_industry_info,
            args_schema=IndustryKeySchema,
        ),
        StructuredTool(
            name="yfinance_search_ticker",
            description="Search for ticker symbols by company name to find the correct stock symbol",
            coroutine=search_ticker,
            args_schema=CompanySearchSchema,
        ),
    ]
