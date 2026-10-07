"""Tests for MarketSeedPipeline, and for the Cloud Computing seed shipped with the module."""

from __future__ import annotations

from pathlib import Path

import pytest
import yaml
from naas_abi_core.services.object_storage.ObjectStorageFactory import (
    ObjectStorageFactory,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.MarketSeedPipeline import (
    MarketSeedPipeline,
    MarketSeedPipelineConfiguration,
    MarketSeedPipelineParameters,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.pipelines.utils.graph_builders import (
    ABI,
    market_uri,
)
from naas_abi_marketplace.domains.intelligence.modules.markets.utils.company_directory import (
    YahooFinanceCompanyDirectory,
)
from rdflib import RDF, Graph

SEED = Path(__file__).parents[1] / "data" / "demo" / "CloudComputing.yaml"

SPEC = {
    "market": {"label": "Cloud Computing", "key": "cloud-computing"},
    "segmentation": {
        "source": {"title": "map"},
        "segments": [
            {"label": "IaaS", "key": "iaas", "criterion": "Service model"},
            {
                "label": "Public Cloud",
                "key": "public-cloud",
                "criterion": "Deployment model",
            },
        ],
    },
    "competitors": [
        {
            "market": "iaas",
            "source": {"title": "SRG"},
            "items": [{"organization": "Amazon"}],
        }
    ],
    "yahoofinance": [
        {
            "market": "public-cloud",
            "tickers": [{"symbol": "OVH.PA", "organization": "OVHcloud"}],
        }
    ],
    "sizes": [
        {
            "market": "public-cloud",
            "value": 1e9,
            "currency": "USD",
            "year": 2025,
            "source": {"title": "G"},
        }
    ],
    "swot": [{"threats": ["Energy prices."], "source": {"title": "S"}}],
}


@pytest.fixture
def storage(tmp_path: Path):
    return ObjectStorageFactory.ObjectStorageServiceFS(str(tmp_path / "datastore"))


def seed(storage, directory=None) -> MarketSeedPipeline:
    return MarketSeedPipeline(
        MarketSeedPipelineConfiguration(
            object_storage=storage, directory=directory, persist=False
        )
    )


def fake_directory() -> YahooFinanceCompanyDirectory:
    return YahooFinanceCompanyDirectory(
        fetch_info=lambda symbol: {
            "longName": f"{symbol} Inc.",
            "website": "https://x.example",
        },
        fetch_peers=lambda key: [],
    )


def test_spec_in_the_datastore_becomes_the_market_graph_next_to_it(storage) -> None:
    storage.put_object(
        "intelligence/markets/CloudComputing",
        "CloudComputing.yaml",
        yaml.safe_dump(SPEC).encode(),
    )
    g = seed(storage, fake_directory()).run(
        MarketSeedPipelineParameters(folder="CloudComputing")
    )

    assert (
        market_uri("cloud-computing"),
        ABI.hasMarketSegment,
        market_uri("iaas"),
    ) in g
    competing = {
        g.value(a, ABI.isInMarket) for a in g.subjects(RDF.type, ABI.ActOfCompeting)
    }
    assert competing == {market_uri("iaas"), market_uri("public-cloud")}
    assert any(g.subjects(RDF.type, ABI.MarketSizeMeasurement))
    assert any(g.subjects(RDF.type, ABI.MarketThreat))

    written = Graph().parse(
        data=storage.get_object(
            "intelligence/markets/CloudComputing", "CloudComputing.ttl"
        ),
        format="turtle",
    )
    assert len(written) == len(g)
    # Quotes are kept under the root market's folder, whichever segment they are for.
    assert storage.get_object(
        "intelligence/markets/CloudComputing/yahoofinance", "OVH.PA.json"
    )


def test_without_a_directory_the_yahoo_section_is_skipped(storage) -> None:
    g = seed(storage).run(MarketSeedPipelineParameters(spec=SPEC))
    competing = {
        g.value(a, ABI.isInMarket) for a in g.subjects(RDF.type, ABI.ActOfCompeting)
    }
    assert competing == {market_uri("iaas")}


def test_a_section_naming_an_unknown_market_is_refused(storage) -> None:
    spec = {
        **SPEC,
        "swot": [{"market": "saas", "threats": ["x"], "source": {"title": "S"}}],
    }
    with pytest.raises(ValueError, match="unknown market 'saas'"):
        seed(storage).run(MarketSeedPipelineParameters(spec=spec))


def test_the_cloud_computing_seed_builds() -> None:
    spec = yaml.safe_load(SEED.read_text())
    g = MarketSeedPipeline(MarketSeedPipelineConfiguration(persist=False)).run(
        MarketSeedPipelineParameters(spec=spec)
    )
    segments = set(g.objects(market_uri("cloud-computing"), ABI.hasMarketSegment))
    assert len(segments) >= 5
    # Every act of the seed cites a source.
    for act_class in (
        ABI.ActOfCompeting,
        ABI.ActOfMarketSegmentation,
        ABI.ActOfMarketSizing,
        ABI.ActOfMarketAnalysis,
    ):
        acts = set(g.subjects(RDF.type, act_class))
        assert acts, act_class
        assert all(g.value(a, ABI.hasMarketSource) is not None for a in acts), act_class
