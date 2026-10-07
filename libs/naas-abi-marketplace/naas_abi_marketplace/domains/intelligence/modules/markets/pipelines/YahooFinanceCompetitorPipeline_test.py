"""Tests for YahooFinanceCompetitorPipeline and the Yahoo Finance company directory."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketCompetitorPipeline import (
    act_of_competing_uri,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    organization_uri,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.YahooFinanceCompetitorPipeline import (
    YahooFinanceCompetitorPipeline,
    YahooFinanceCompetitorPipelineConfiguration,
    YahooFinanceCompetitorPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.company_directory import (
    CompanyNotFoundError,
    IndustryPeer,
    YahooFinanceCompanyDirectory,
)
from rdflib import RDF

INFO = {
    "OVH.PA": {
        "longName": "OVH Groupe S.A.",
        "website": "https://www.ovhcloud.com",
        "country": "France",
        "industry": "Software - Infrastructure",
        "industryKey": "software-infrastructure",
        "totalRevenue": 1103900032,
    },
    "AMZN": {"longName": "Amazon.com, Inc.", "website": "https://www.aboutamazon.com"},
}


def directory() -> YahooFinanceCompanyDirectory:
    return YahooFinanceCompanyDirectory(
        fetch_info=lambda symbol: INFO.get(symbol, {"trailingPegRatio": None}),
        fetch_peers=lambda key: [
            IndustryPeer("MSFT", "Microsoft Corporation", 0.6),
            IndustryPeer("PANW", "Palo Alto Networks, Inc.", 0.05),
        ],
    )


@pytest.fixture
def storage(tmp_path: Path):
    return ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path / "datastore"))


def pipeline(storage=None) -> YahooFinanceCompetitorPipeline:
    return YahooFinanceCompetitorPipeline(
        YahooFinanceCompetitorPipelineConfiguration(
            directory=directory(), object_storage=storage, persist=False
        )
    )


def params(tickers) -> YahooFinanceCompetitorPipelineParameters:
    return YahooFinanceCompetitorPipelineParameters.model_validate(
        {
            "market": {"label": "Cloud Computing", "key": "cloud-computing"},
            "tickers": tickers,
        }
    )


def test_listed_company_is_registered_and_cited_to_its_quote_page(storage) -> None:
    g = pipeline(storage).run(
        params([{"symbol": "OVH.PA", "organization": "OVHcloud", "region": "Europe"}])
    )
    act = act_of_competing_uri("OVHcloud", "cloud-computing", "Europe")
    assert (act, RDF.type, ABI.ActOfCompeting) in g
    assert (act, ABI.hasCompetitor, organization_uri("OVHcloud")) in g
    source = g.value(act, ABI.hasMarketSource)
    assert (
        str(g.value(source, ABI.market_source_url))
        == "https://finance.yahoo.com/quote/OVH.PA/"
    )
    assert str(g.value(source, ABI.market_source_publisher)) == "Yahoo Finance"
    org = organization_uri("OVHcloud")
    assert (
        str(g.value(g.value(org, ABI.hasTickerSymbol), ABI.ticker_symbol)) == "OVH.PA"
    )
    assert (
        str(g.value(g.value(org, ABI.hasWebsite), ABI.website_url))
        == "https://www.ovhcloud.com"
    )


def test_without_a_label_the_yahoo_name_is_used(storage) -> None:
    g = pipeline(storage).run(params([{"symbol": "AMZN"}]))
    assert g.value(organization_uri("Amazon.com, Inc."), ABI.isCompetitorIn) is not None


def test_what_was_read_is_kept_under_the_market_folder(storage) -> None:
    pipeline(storage).run(params([{"symbol": "OVH.PA"}]))
    raw = storage.get_object(
        "intelligence/markets/CloudComputing/yahoofinance", "OVH.PA.json"
    )
    assert json.loads(raw)["longName"] == "OVH Groupe S.A."


def test_unknown_symbol_is_an_error_not_an_empty_company() -> None:
    with pytest.raises(CompanyNotFoundError):
        pipeline().run(params([{"symbol": "NOPE"}]))


def test_industry_candidates_are_listed_not_registered() -> None:
    candidates = pipeline().industry_candidates("OVH.PA")
    assert [c["symbol"] for c in candidates] == ["MSFT", "PANW"]
    assert candidates[0]["industry"] == "Software - Infrastructure"
