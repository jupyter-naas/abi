"""Offline tests of the Yahoo Finance integration: fake yfinance and search."""

from __future__ import annotations

import asyncio
import json
import threading
from types import SimpleNamespace

import pandas as pd
import pytest
from naas_abi_apps.common.testing import MemoryStorage
from naas_abi_apps.yahoofinance.integrations.YfinanceIntegration import (
    YfinanceIntegration,
    YfinanceIntegrationConfiguration,
    as_tools,
    frame_to_records,
    to_json,
)
from naas_abi_sdk.integration import IntegrationConnectionError

MAIN = threading.main_thread()


class FakeTicker:
    def __init__(self, symbol: str) -> None:
        if symbol == "BAD":
            raise ValueError("unknown ticker")
        # The blocking library must run off the event loop thread.
        assert threading.current_thread() is not MAIN
        self.info = {"symbol": symbol, "listed": pd.Timestamp("2020-01-01")}
        self.quarterly_income_stmt = pd.DataFrame(
            {"Total Revenue": [1.0]}, index=["2026Q1"]
        )
        self.calendar = {"Earnings Date": [pd.Timestamp("2026-02-01")]}
        self.analyst_price_targets = {"mean": 10.0}

    def history(self, period: str) -> pd.DataFrame:
        index = pd.DatetimeIndex(["2026-01-02", "2026-01-03"])
        return pd.DataFrame({"Close": [1.0, float("nan")]}, index=index)


FAKE_YF = SimpleNamespace(Ticker=FakeTicker)


def integration(storage=None) -> YfinanceIntegration:
    return YfinanceIntegration(
        YfinanceIntegrationConfiguration(
            storage=storage,
            yfinance=lambda: FAKE_YF,
            search=lambda q: {"quotes": [{"symbol": "AAPL", "shortname": q}]},
        )
    )


def test_history_is_records_with_iso_keys_and_is_archived() -> None:
    storage = MemoryStorage()
    history = asyncio.run(integration(storage).get_ticker_history("AAPL", "5d"))

    assert history == [
        {"key": "2026-01-02T00:00:00", "close": 1.0},
        {"key": "2026-01-03T00:00:00", "close": 0.0},
    ]
    stored = storage.objects[("yahoofinance/tickers/AAPL", "AAPL_history_5d.json")]
    assert json.loads(stored) == history


def test_info_and_financials_are_json() -> None:
    info = asyncio.run(integration().get_ticker_info("AAPL"))
    financials = asyncio.run(integration().get_ticker_financials("AAPL"))

    assert info == {"symbol": "AAPL", "listed": "2020-01-01T00:00:00"}
    assert financials["quarterly_income_stmt"] == [
        {"key": "2026Q1", "total_revenue": 1.0}
    ]
    assert financials["calendar"] == [{"Earnings Date": ["2026-02-01T00:00:00"]}]
    json.dumps(financials)


def test_library_errors_are_connection_errors() -> None:
    with pytest.raises(IntegrationConnectionError, match="ticker info for BAD"):
        asyncio.run(integration().get_ticker_info("BAD"))


def test_search_and_tool_names() -> None:
    assert asyncio.run(integration().search_ticker("Apple")) == [
        {"symbol": "AAPL", "shortname": "Apple"}
    ]
    names = {t.name for t in as_tools(integration().configuration)}
    assert names == {
        "yfinance_get_ticker_info",
        "yfinance_get_ticker_history",
        "yfinance_get_ticker_financials",
        "yfinance_get_sector_info",
        "yfinance_get_industry_info",
        "yfinance_search_ticker",
    }


def test_helpers() -> None:
    assert frame_to_records(None) == []
    assert to_json({"a": [float("nan"), pd.Timestamp("2026-01-01")]}) == {
        "a": [None, "2026-01-01T00:00:00"]
    }
