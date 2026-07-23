"""Unit tests for the X post-count app hub (slugify, render, timeseries SPARQL).

The timeseries test runs the hub's real SPARQL against an rdflib-backed fake
triple store loaded with the exact graph shape XCountRecentTweetsPipeline emits,
so it doubles as a check of the ontology↔SPARQL contract.
"""

from datetime import datetime, timezone

from naas_abi_marketplace.applications.x.apps.x.hub import (
    XCountAppHubBuilder,
    render_index,
    slugify,
)
from naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcessOntology import (  # noqa: E501
    CountInterval,
    TweetCountBucket,
    TweetCountResultSet,
)
from rdflib import Dataset, Graph, URIRef

_NS = "http://ontology.naas.ai/x/"
_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
_QUERY = "(drone OR uas) lang:en -is:retweet"


class _FakeTripleStore:
    """Minimal triple store backed by a real rdflib Dataset."""

    def __init__(self) -> None:
        self.dataset = Dataset()

    def insert_graph(self, graph: Graph, graph_name: str) -> None:
        named = self.dataset.graph(URIRef(graph_name))
        for triple in graph:
            named.add(triple)

    def query(self, sparql: str):
        return self.dataset.query(sparql)


def _seed_store() -> _FakeTripleStore:
    graph = Graph()
    buckets = [
        ("2026-07-07T12:00:00+00:00", "2026-07-07T13:00:00+00:00", 10),
        ("2026-07-07T13:00:00+00:00", "2026-07-07T14:00:00+00:00", 22),
    ]
    bucket_uris: list = []
    for start, end, count in buckets:
        stable = f"drones-{start}"
        interval = CountInterval(
            _uri=f"{_NS}CountInterval/{stable}",
            label=f"Count Interval drones {start}",
            bucket_start=datetime.fromisoformat(start),
            bucket_end=datetime.fromisoformat(end),
        )
        graph += interval.rdf()
        bucket = TweetCountBucket(
            _uri=f"{_NS}TweetCountBucket/{stable}",
            label=f"Tweet Count Bucket drones {start}",
            bucket_tweet_count=count,
            has_count_interval=[URIRef(interval._uri)],
        )
        graph += bucket.rdf()
        bucket_uris.append(URIRef(bucket._uri))
    result_set = TweetCountResultSet(
        _uri=f"{_NS}TweetCountResultSet/abc123",
        label="Tweet Count Result Set abc123",
        query_string=_QUERY,
        granularity="hour",
        total_tweet_count=32,
        file_path="x/count_recent_tweets/drones/f.json",
        contains_count_bucket=bucket_uris,
    )
    graph += result_set.rdf()

    store = _FakeTripleStore()
    store.insert_graph(graph, _GRAPH)
    return store


def test_slugify_is_stable_and_filesystem_safe():
    assert slugify(_QUERY) == "drone_or_uas_lang_en_is_retweet"
    assert slugify("  ") == "query"
    assert "__" not in slugify("a???b")


def test_timeseries_returns_sorted_hourly_buckets():
    store = _seed_store()
    hub = XCountAppHubBuilder(
        object_storage_service=None,  # not used by _timeseries
        triple_store=store,  # type: ignore[arg-type]
    )
    series = hub._timeseries(_QUERY)
    assert [b["count"] for b in series] == [10, 22]
    assert series[0]["start"].startswith("2026-07-07T12:00:00")
    assert series[1]["end"].startswith("2026-07-07T14:00:00")


def test_timeseries_unknown_query_is_empty():
    store = _seed_store()
    hub = XCountAppHubBuilder(None, store)  # type: ignore[arg-type]
    assert hub._timeseries("something else entirely") == []


def test_render_index_embeds_series_and_fills_placeholders():
    series = [
        {
            "slug": "drones",
            "query": _QUERY,
            "label": "Drones",
            "granularity": "hour",
            "updated_at": "2026-07-07T14:00:00+00:00",
            "buckets": [
                {"start": "2026-07-07T13:00:00+00:00", "end": None, "count": 22}
            ],
        }
    ]
    html = render_index(series, datetime(2026, 7, 7, 14, 0, tzinfo=timezone.utc))
    assert "<!doctype html>" in html
    assert "__DATA_JSON__" not in html and "__BUILT_AT__" not in html
    # X theme + both dropdowns + KPI labels present.
    assert "#1d9bf0" in html and "Last 24 hours" in html and "Last 30 days" in html
    assert "drones" in html and "Peak" in html and "Lowest" in html
