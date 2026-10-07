"""Tests for MarketCompetitorPipeline."""

from __future__ import annotations

from decimal import Decimal

import pytest
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketCompetitorPipeline import (
    MarketCompetitorPipeline,
    MarketCompetitorPipelineConfiguration,
    MarketCompetitorPipelineParameters,
    act_of_competing_uri,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    market_uri,
    organization_uri,
)
from naas_abi_marketplace.domains.intelligence.modules.organizations.pipelines.OrganizationLogoPipeline import (
    organization_uri as organizations_module_uri,
)
from rdflib import RDF, RDFS, Literal

SRG = {
    "title": "Cloud Market Share Trends - Q3 2025",
    "url": "https://srgresearch.com/articles/x",
    "publisher": "Synergy Research Group",
    "date": "2025-11-19",
}


class FakeTripleStore:
    def __init__(self) -> None:
        self.inserted: list = []

    def insert(self, graph, graph_name=None) -> None:
        self.inserted.append((len(graph), graph_name))


def run(competitors, source=SRG, triple_store=None):
    return MarketCompetitorPipeline(
        MarketCompetitorPipelineConfiguration(triple_store=triple_store)
    ).run(
        MarketCompetitorPipelineParameters.model_validate(
            {
                "market": {"label": "IaaS", "key": "iaas"},
                "competitors": competitors,
                "source": source,
            }
        )
    )


def test_competitor_is_the_same_organization_the_other_modules_mint() -> None:
    assert organization_uri("OVHcloud") == organizations_module_uri("OVHcloud")
    assert organization_uri("Amazon Web Services") == organizations_module_uri(
        "Amazon Web Services"
    )


def test_act_of_competing_ties_the_seven_buckets() -> None:
    g = run([{"organization": "OVHcloud", "region": "Europe", "period": "2026"}])
    act = act_of_competing_uri("OVHcloud", "iaas", "Europe")
    org = organization_uri("OVHcloud")
    assert (act, RDF.type, ABI.ActOfCompeting) in g
    assert (act, ABI.hasCompetitor, org) in g
    assert (act, ABI.isInMarket, market_uri("iaas")) in g
    assert g.value(g.value(act, ABI.occursIn), RDFS.label) == Literal("Europe")
    assert g.value(g.value(act, ABI.occupiesTemporalRegion), RDFS.label) == Literal(
        "2026"
    )
    role = g.value(act, ABI.realizes)
    assert (role, RDF.type, ABI.CompetitorRole) in g
    assert (role, ABI.inheresIn, org) in g
    source = g.value(act, ABI.hasMarketSource)
    assert g.value(source, ABI.market_source_url) is not None
    # The one-hop shortcut
    assert (org, ABI.hasMarket, market_uri("iaas")) in g


def test_share_and_rank_are_a_measurement_of_the_act() -> None:
    g = run(
        [
            {
                "organization": "Amazon",
                "period": "Q3 2025",
                "share_percent": "29",
                "rank": 1,
            },
            {"organization": "Alibaba", "period": "Q3 2025", "rank": 4},
            {"organization": "OVHcloud"},
        ]
    )
    amazon = act_of_competing_uri("Amazon", "iaas", "Global")
    measurement = g.value(amazon, ABI.hasMarketShareMeasurement)
    assert (measurement, RDF.type, ABI.MarketShareMeasurement) in g
    assert g.value(measurement, ABI.market_share_percent).toPython() == Decimal(29)
    assert g.value(measurement, ABI.market_rank).toPython() == 1
    alibaba = g.value(
        act_of_competing_uri("Alibaba", "iaas", "Global"), ABI.hasMarketShareMeasurement
    )
    assert g.value(alibaba, ABI.market_share_percent) is None
    assert (
        g.value(
            act_of_competing_uri("OVHcloud", "iaas", "Global"),
            ABI.hasMarketShareMeasurement,
        )
        is None
    )


def test_website_and_ticker_use_the_organizations_vocabulary() -> None:
    g = run(
        [
            {
                "organization": "OVHcloud",
                "website": "https://www.ovhcloud.com",
                "ticker": "OVH.PA",
            }
        ]
    )
    org = organization_uri("OVHcloud")
    assert (
        str(g.value(g.value(org, ABI.hasWebsite), ABI.website_url))
        == "https://www.ovhcloud.com"
    )
    assert (
        str(g.value(g.value(org, ABI.hasTickerSymbol), ABI.ticker_symbol)) == "OVH.PA"
    )


def test_competitors_are_never_linked_to_each_other() -> None:
    g = run([{"organization": "Amazon"}, {"organization": "Microsoft"}])
    amazon, microsoft = organization_uri("Amazon"), organization_uri("Microsoft")
    assert not any(True for _ in g.triples((amazon, None, microsoft)))
    assert not any(True for _ in g.triples((microsoft, None, amazon)))


def test_a_competitor_without_a_source_is_refused() -> None:
    with pytest.raises(ValueError, match="no source"):
        run([{"organization": "OVHcloud"}], source=None)


def test_persists_into_the_markets_graph() -> None:
    store = FakeTripleStore()
    graph = run([{"organization": "OVHcloud"}], triple_store=store)
    assert len(store.inserted) == 1
    size, graph_name = store.inserted[0]
    assert size == len(graph)
    assert str(graph_name) == "http://ontology.naas.ai/graph/markets"
