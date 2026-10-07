"""Tests for MarketAnalysisPipeline (SWOT)."""

from __future__ import annotations

import pytest
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketAnalysisPipeline import (
    MarketAnalysisPipeline,
    MarketAnalysisPipelineConfiguration,
    MarketAnalysisPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    market_uri,
    organization_uri,
)
from pydantic import ValidationError
from rdflib import RDF

SOURCE = {"title": "Cloud Computing market review 2026", "publisher": "Forvis Mazars"}


def run(**overrides):
    return MarketAnalysisPipeline(
        MarketAnalysisPipelineConfiguration(persist=False)
    ).run(
        MarketAnalysisPipelineParameters.model_validate(
            {
                "market": {"label": "Cloud Computing", "key": "cloud-computing"},
                "opportunities": ["AI workloads drive GPU demand."],
                "threats": ["Grid capacity constrains new data centers."],
                "strengths": [
                    {
                        "organization": "OVHcloud",
                        "statement": "Vertically integrated, low unit costs.",
                    }
                ],
                "weaknesses": [
                    {
                        "organization": "OVHcloud",
                        "statement": "Narrower managed-service catalogue.",
                    }
                ],
                "analyst": "Forvis Mazars",
                "region": "Europe",
                "period": "2026",
                "source": SOURCE,
                **overrides,
            }
        )
    )


def findings(g, class_uri):
    return set(g.subjects(RDF.type, class_uri))


def test_opportunities_and_threats_are_about_the_market_only() -> None:
    g = run()
    market = market_uri("cloud-computing")
    for class_uri in (ABI.MarketOpportunity, ABI.MarketThreat):
        (finding,) = findings(g, class_uri)
        assert (finding, ABI.isFindingAboutMarket, market) in g
        assert g.value(finding, ABI.isFindingAboutOrganization) is None


def test_strengths_and_weaknesses_name_the_competitor_and_the_market() -> None:
    g = run()
    ovh = organization_uri("OVHcloud")
    for class_uri in (ABI.CompetitiveStrength, ABI.CompetitiveWeakness):
        (finding,) = findings(g, class_uri)
        assert (finding, ABI.isFindingAboutOrganization, ovh) in g
        assert (finding, ABI.isFindingAboutMarket, market_uri("cloud-computing")) in g


def test_every_finding_is_a_swot_finding_of_one_cited_act() -> None:
    g = run()
    all_findings = findings(g, ABI.SWOTFinding)
    assert len(all_findings) == 4
    (act,) = g.subjects(RDF.type, ABI.ActOfMarketAnalysis)
    assert set(g.objects(act, ABI.hasSWOTFinding)) == all_findings
    assert g.value(act, ABI.hasMarketSource) is not None
    statement = g.value(
        next(iter(findings(g, ABI.MarketThreat))), ABI.finding_statement
    )
    assert str(statement) == "Grid capacity constrains new data centers."


def test_an_analysis_without_findings_is_refused() -> None:
    with pytest.raises(ValidationError, match="at least one finding"):
        run(opportunities=[], threats=[], strengths=[], weaknesses=[])
