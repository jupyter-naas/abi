"""Tests for MarketSizingPipeline."""

from __future__ import annotations

from decimal import Decimal

import pytest
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSizingPipeline import (
    MarketSizingPipeline,
    MarketSizingPipelineConfiguration,
    MarketSizingPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    market_uri,
)
from pydantic import ValidationError
from rdflib import RDF, RDFS, Graph, Literal

GARTNER = {
    "title": "Gartner Forecasts Worldwide Public Cloud End-User Spending to Total $723 Billion in 2025",
    "url": "https://www.gartner.com/en/newsroom/press-releases/2024-11-19-x",
    "publisher": "Gartner",
    "date": "2024-11-19",
}


def params(**overrides) -> MarketSizingPipelineParameters:
    return MarketSizingPipelineParameters.model_validate(
        {
            "market": {"label": "Public Cloud", "key": "public-cloud"},
            "value": "723400000000",
            "currency": "USD",
            "year": 2025,
            "growth_rate_percent": "21.5",
            "growth_period": "2024-2025",
            "analyst": "Gartner",
            "source": GARTNER,
            **overrides,
        }
    )


def run(p: MarketSizingPipelineParameters) -> Graph:
    return MarketSizingPipeline(MarketSizingPipelineConfiguration(persist=False)).run(p)


def test_size_is_a_measurement_of_the_market_by_an_act_of_sizing() -> None:
    g = run(params())
    (measurement,) = g.subjects(RDF.type, ABI.MarketSizeMeasurement)
    assert (measurement, ABI.measuresMarket, market_uri("public-cloud")) in g
    assert g.value(measurement, ABI.market_size_value).toPython() == Decimal(
        723400000000
    )
    assert str(g.value(measurement, ABI.market_size_currency)) == "USD"
    assert g.value(measurement, ABI.market_size_year).toPython() == 2025
    assert g.value(measurement, ABI.market_growth_rate_percent).toPython() == Decimal(
        "21.5"
    )
    assert "USD 723.4B" in str(g.value(measurement, RDFS.label))

    act = g.value(measurement, ABI.isMarketSizeMeasurementOf)
    assert (act, RDF.type, ABI.ActOfMarketSizing) in g
    assert g.value(g.value(act, ABI.hasParticipant), RDFS.label) == Literal("Gartner")
    assert g.value(g.value(act, ABI.occursIn), RDFS.label) == Literal("Global")
    assert g.value(g.value(act, ABI.occupiesTemporalRegion), RDFS.label) == Literal(
        "2025"
    )
    assert str(
        g.value(g.value(act, ABI.hasMarketSource), ABI.market_source_url)
    ).startswith("https://www.gartner.com/")


def test_two_sources_give_two_sizings_neither_overwrites() -> None:
    g = run(params())
    g += run(
        params(
            value="390000000000",
            analyst="Synergy Research Group",
            source={"title": "SRG Q3 2025", "url": "https://srgresearch.com/x"},
        )
    )
    assert len(set(g.subjects(RDF.type, ABI.MarketSizeMeasurement))) == 2
    assert len(set(g.subjects(RDF.type, ABI.ActOfMarketSizing))) == 2


def test_currency_must_be_an_iso_code() -> None:
    with pytest.raises(ValidationError):
        params(currency="dollars")
