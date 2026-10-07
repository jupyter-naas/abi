"""Tests for MarketSegmentationPipeline."""

from __future__ import annotations

import pytest
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSegmentationPipeline import (
    MarketSegmentationPipeline,
    MarketSegmentationPipelineConfiguration,
    MarketSegmentationPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    individual_uri,
    market_uri,
)
from pydantic import ValidationError
from rdflib import DCTERMS, RDF, RDFS, Literal

SOURCE = {"title": "Cloud Computing market map", "publisher": "Forvis Mazars"}


def params(**overrides) -> MarketSegmentationPipelineParameters:
    data = {
        "market": {"label": "Cloud Computing", "key": "cloud-computing"},
        "segments": [
            {"label": "IaaS", "key": "iaas", "criterion": "Service model"},
            {
                "label": "Public Cloud",
                "key": "public-cloud",
                "criterion": "Deployment model",
            },
            {
                "label": "Private Cloud",
                "key": "private-cloud",
                "criterion": "Deployment model",
            },
            {
                "label": "GPU cloud",
                "key": "gpu-cloud",
                "criterion": "Workload",
                "parents": ["iaas", "Public Cloud"],
            },
        ],
        "analyst": "Forvis Mazars",
        "period": "2026",
        "source": SOURCE,
        **overrides,
    }
    return MarketSegmentationPipelineParameters.model_validate(data)


def run(p: MarketSegmentationPipelineParameters):
    return MarketSegmentationPipeline(
        MarketSegmentationPipelineConfiguration(persist=False)
    ).run(p)


def test_segments_belong_to_the_market_by_default() -> None:
    g = run(params())
    market, iaas = market_uri("cloud-computing"), market_uri("iaas")
    assert (market, RDF.type, ABI.Market) in g
    assert (iaas, RDF.type, ABI.MarketSegment) in g
    # No reasoner downstream: a segment is typed as a market too.
    assert (iaas, RDF.type, ABI.Market) in g
    assert (market, ABI.hasMarketSegment, iaas) in g
    assert (iaas, ABI.isMarketSegmentOf, market) in g
    assert g.value(market, RDFS.label) == Literal("Cloud Computing")


def test_a_segment_may_have_several_parents_and_names_its_criterion() -> None:
    g = run(params())
    gpu = market_uri("gpu-cloud")
    assert set(g.objects(gpu, ABI.isMarketSegmentOf)) == {
        market_uri("iaas"),
        market_uri("public-cloud"),
    }
    assert (market_uri("cloud-computing"), ABI.hasMarketSegment, gpu) not in g
    criterion = individual_uri("SegmentationCriterion", "workload")
    assert (gpu, ABI.hasSegmentationCriterion, criterion) in g
    assert g.value(criterion, RDFS.label) == Literal("Workload")


def test_one_act_per_parent_and_criterion_cites_its_source() -> None:
    g = run(params())
    acts = set(g.subjects(RDF.type, ABI.ActOfMarketSegmentation))
    # cloud-computing x {service model, deployment model}; iaas x workload; public-cloud x workload
    assert len(acts) == 4
    deployment = individual_uri(
        "ActOfMarketSegmentation", "cloud-computing-deployment-model"
    )
    assert set(g.objects(deployment, ABI.yieldsMarketSegment)) == {
        market_uri("public-cloud"),
        market_uri("private-cloud"),
    }
    assert (deployment, ABI.segmentsMarket, market_uri("cloud-computing")) in g
    source = g.value(deployment, ABI.hasMarketSource)
    assert (source, RDF.type, ABI.MarketSource) in g
    assert str(g.value(source, ABI.market_source_publisher)) == "Forvis Mazars"
    analyst = g.value(deployment, ABI.hasParticipant)
    assert g.value(analyst, RDFS.label) == Literal("Forvis Mazars")
    assert (g.value(deployment, ABI.realizes), RDF.type, ABI.MarketAnalystRole) in g


def test_running_twice_writes_the_same_triples() -> None:
    first = run(params())
    second = run(params())

    def stable(g):
        return {t for t in g if t[1] != DCTERMS.created}

    assert stable(first) == stable(second)


def test_unknown_parent_is_refused() -> None:
    with pytest.raises(ValidationError, match="unknown parent"):
        params(
            segments=[
                {"label": "GPU cloud", "criterion": "Workload", "parents": ["nope"]}
            ]
        )
