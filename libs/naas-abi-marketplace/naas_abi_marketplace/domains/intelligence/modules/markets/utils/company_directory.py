"""Company directory port, and its Yahoo Finance adapter.

The markets pipelines need two things from a market-data provider: the profile
of a listed company (name, website, headquarters, industry, size) and the
companies a provider files under the same industry. Pipelines depend on the
port; tests pass a fake, the agent and the seed pass the Yahoo Finance adapter.

Yahoo's industries are broad: ``software-infrastructure`` holds OVHcloud and
Microsoft but also Palo Alto Networks and CrowdStrike. Industry peers are
therefore candidates to review, never competitors registered as such.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CompanyProfile:
    symbol: str
    name: str
    website: str | None = None
    country: str | None = None
    city: str | None = None
    sector: str | None = None
    industry: str | None = None
    industry_key: str | None = None
    currency: str | None = None
    market_cap: float | None = None
    total_revenue: float | None = None
    employees: int | None = None
    summary: str | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def quote_url(self) -> str:
        return f"https://finance.yahoo.com/quote/{self.symbol}/"

    @classmethod
    def from_yahoo(cls, symbol: str, info: dict[str, Any]) -> CompanyProfile:
        return cls(
            symbol=symbol,
            name=info.get("longName") or info.get("shortName") or symbol,
            website=info.get("website"),
            country=info.get("country"),
            city=info.get("city"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            industry_key=info.get("industryKey"),
            currency=info.get("financialCurrency") or info.get("currency"),
            market_cap=info.get("marketCap"),
            total_revenue=info.get("totalRevenue"),
            employees=info.get("fullTimeEmployees"),
            summary=info.get("longBusinessSummary"),
            raw=info,
        )


@dataclass
class IndustryPeer:
    symbol: str
    name: str
    market_weight: float | None = None


class CompanyNotFoundError(LookupError):
    pass


class CompanyDirectoryPort(ABC):
    @abstractmethod
    def company(self, symbol: str) -> CompanyProfile:
        """Profile of the listed company; ``CompanyNotFoundError`` when unknown."""

    @abstractmethod
    def industry_peers(self, industry_key: str) -> list[IndustryPeer]:
        """Largest companies the provider files under the industry."""


def _yahoo_info(symbol: str) -> dict[str, Any]:
    """Ticker info through the yahoofinance integration when its module is loaded.

    The integration caches and stores what it reads under its own datastore;
    outside a loaded engine (a script, a test run) yfinance is called directly.
    """
    try:
        from naas_abi_marketplace.applications.yahoofinance import (
            ABIModule as YahooFinanceModule,
        )
        from naas_abi_marketplace.applications.yahoofinance.integrations.YfinanceIntegration import (
            YfinanceIntegration,
            YfinanceIntegrationConfiguration,
        )

        YahooFinanceModule.get_instance()
        return YfinanceIntegration(YfinanceIntegrationConfiguration()).get_ticker_info(
            symbol
        )
    except Exception:  # noqa: BLE001 - module not loaded: fall back to the library
        import yfinance as yf  # type: ignore

        return yf.Ticker(symbol).info


def _yahoo_peers(industry_key: str) -> list[IndustryPeer]:
    import yfinance as yf  # type: ignore

    top = yf.Industry(industry_key).top_companies
    if top is None:
        return []
    return [
        IndustryPeer(
            symbol=str(symbol),
            name=str(row.get("name") or symbol),
            market_weight=float(row["market weight"])
            if "market weight" in row
            else None,
        )
        for symbol, row in top.iterrows()
    ]


class YahooFinanceCompanyDirectory(CompanyDirectoryPort):
    def __init__(
        self,
        fetch_info: Callable[[str], dict[str, Any]] = _yahoo_info,
        fetch_peers: Callable[[str], list[IndustryPeer]] = _yahoo_peers,
    ):
        self._fetch_info = fetch_info
        self._fetch_peers = fetch_peers

    def company(self, symbol: str) -> CompanyProfile:
        info = self._fetch_info(symbol) or {}
        # Yahoo answers an unknown symbol with a near-empty dict, not an error.
        if not (info.get("longName") or info.get("shortName")):
            raise CompanyNotFoundError(f"Yahoo Finance knows no company for '{symbol}'")
        return CompanyProfile.from_yahoo(symbol, info)

    def industry_peers(self, industry_key: str) -> list[IndustryPeer]:
        return self._fetch_peers(industry_key)
