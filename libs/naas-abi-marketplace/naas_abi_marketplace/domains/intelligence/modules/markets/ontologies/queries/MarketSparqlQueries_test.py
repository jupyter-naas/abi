"""The markets SPARQL queries: well-formed, and answering on the Cloud Computing seed."""

from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml
from jinja2 import Template
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSeedPipeline import (
    MarketSeedPipeline,
    MarketSeedPipelineConfiguration,
    MarketSeedPipelineParameters,
)
from rdflib import RDFS, Dataset, Graph, Namespace, URIRef

HERE = Path(__file__).parent
QUERIES = HERE / "MarketSparqlQueries.ttl"
SEED = HERE.parents[1] / "data" / "demo" / "CloudComputing.yaml"
IM = Namespace("http://ontology.naas.ai/intentMapping/")
GRAPH = URIRef("http://ontology.naas.ai/graph/markets")


@pytest.fixture(scope="module")
def queries() -> dict[str, tuple[str, set[str]]]:
    g = Graph().parse(QUERIES)
    out = {}
    for query in g.subjects(IM.sparqlTemplate, None):
        args = {
            str(g.value(a, IM.argumentName)) for a in g.objects(query, IM.hasArgument)
        }
        out[str(g.value(query, RDFS.label))] = (
            str(g.value(query, IM.sparqlTemplate)),
            args,
        )
    return out


@pytest.fixture(scope="module")
def dataset() -> Dataset:
    # Offline: without a company directory the Yahoo Finance section is skipped.
    graph = MarketSeedPipeline(MarketSeedPipelineConfiguration(persist=False)).run(
        MarketSeedPipelineParameters(spec=yaml.safe_load(SEED.read_text()))
    )
    ds = Dataset()
    ds.graph(GRAPH).__iadd__(graph)
    return ds


def rows(dataset, template: str, **args) -> list:
    return list(dataset.query(Template(template).render(limit="200", **args)))


def test_every_placeholder_has_a_declared_argument(queries) -> None:
    assert len(queries) == 7
    for name, (template, args) in queries.items():
        placeholders = set(re.findall(r"\{\{\s*(\w+)\s*\}\}", template))
        assert placeholders == args, name


def test_segments_competitors_sizes_and_swot_of_cloud_computing(
    queries, dataset
) -> None:
    market = {"market_name": "cloud computing"}
    segments = {
        str(r.segmentLabel)
        for r in rows(dataset, queries["find_market_segments"][0], **market)
    }
    assert {
        "Public Cloud",
        "Private Cloud",
        "AI infrastructure / GPU cloud",
    } <= segments

    competitors = rows(dataset, queries["find_market_competitors"][0], **market)
    leader = next(r for r in competitors if r.rank is not None and int(r.rank) == 1)
    assert str(leader.organizationLabel) == "Amazon"
    assert float(leader.sharePercent) == 29
    assert all(r.sourceTitle is not None for r in competitors)

    sizes = rows(dataset, queries["find_market_sizes"][0], **market)
    assert {str(r.analystLabel) for r in sizes} == {"Gartner", "Synergy Research Group"}

    kinds = {
        str(r.kind) for r in rows(dataset, queries["find_market_swot"][0], **market)
    }
    assert kinds == {"Strength", "Weakness", "Opportunity", "Threat"}


def test_a_segment_name_narrows_the_answer(queries, dataset) -> None:
    competitors = rows(
        dataset, queries["find_market_competitors"][0], market_name="gpu"
    )
    assert {str(r.segmentLabel) for r in competitors} == {
        "AI infrastructure / GPU cloud"
    }


def test_competitors_of_an_organization_share_a_market(queries, dataset) -> None:
    found = rows(
        dataset,
        queries["find_competitors_of_organization"][0],
        organization_name="amazon",
    )
    labels = {str(r.competitorLabel) for r in found}
    assert {"Microsoft", "Google"} <= labels
    assert "Amazon" not in labels
    markets = rows(
        dataset,
        queries["find_markets_of_organization"][0],
        organization_name="scaleway",
    )
    assert [str(r.marketLabel) for r in markets] == ["Public Cloud"]


def test_find_markets_resolves_a_segment_with_its_parents(queries, dataset) -> None:
    (row,) = rows(dataset, queries["find_markets"][0], market_name="gpu")
    assert set(str(row.parentMarkets).split(" | ")) == {
        "Cloud Infrastructure / IaaS (Infrastructure-as-a-Service)",
        "Public Cloud",
    }
    assert str(row.criterion) == "Workload"
