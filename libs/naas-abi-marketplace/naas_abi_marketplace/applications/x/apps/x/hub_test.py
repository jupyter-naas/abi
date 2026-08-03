"""Unit tests for the X Recent Tweets app hub + api SPARQL helpers."""

from datetime import UTC, datetime
from pathlib import Path

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    build_scenarios,
    slugify,
)
from naas_abi_marketplace.applications.x.apps.x.hub import XAppHubBuilder
from naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcessOntology import (
    CountInterval,
    TweetCountBucket,
    TweetCountResultSet,
)
from rdflib import RDF, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

_NS = "http://ontology.naas.ai/x/"
_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
_TWEET_GRAPH = "http://ontology.naas.ai/graph/x"
_QUERY = "(drone OR uas) lang:en -is:retweet"
_X = Namespace(_NS)


class _FakeTripleStore:
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


def _seed_tweets(store: "_FakeTripleStore") -> None:
    g = Graph()
    sq, proc, rs = (
        _X["SearchQuery/q1"],
        _X["SearchRecentTweets/p1"],
        _X["SearchResultSet/r1"],
    )
    tw, au = _X["Tweet/1"], _X["XUser/9"]
    g.add((sq, RDF.type, _X.SearchQuery))
    g.add((sq, _X.query_string, Literal(_QUERY)))
    g.add((proc, RDF.type, _X.SearchRecentTweets))
    g.add((proc, _X.usesSearchQuery, sq))
    g.add((proc, _X.producesSearchResult, rs))
    g.add((tw, RDF.type, _X.Tweet))
    g.add((tw, _X.isContainedInSearchResultSet, rs))
    g.add(
        (
            tw,
            _X.tweet_created_at,
            Literal("2026-07-07T13:30:00+00:00", datatype=XSD.dateTime),
        )
    )
    g.add((tw, _X.full_text, Literal("Big drone sighting near the port")))
    g.add((tw, _X.url, Literal("https://x.com/9/status/1")))
    g.add((tw, _X.isAuthoredBy, au))
    g.add((au, _X.username, Literal("dronewatch")))
    g.add((au, _X.user_location, Literal("Ankara")))
    g.add((au, _X.verified_type, Literal("blue")))
    store.insert_graph(g, _TWEET_GRAPH)


def test_slugify_is_stable_and_filesystem_safe():
    assert slugify(_QUERY) == "drone_or_uas_lang_en_is_retweet"
    assert slugify("  ") == "query"
    assert "__" not in slugify("a???b")


def test_build_scenarios_has_id_label_start_end():
    scenarios = build_scenarios(datetime(2026, 7, 7, 14, 0, tzinfo=UTC))
    assert len(scenarios) == 4
    for s in scenarios:
        assert set(s) == {"id", "label", "start_time", "end_time"}
    assert [s["id"] for s in scenarios] == ["24h", "48h", "7d", "30d"]


def test_timeseries_returns_sorted_hourly_buckets():
    store = _seed_store()
    hub = XAppHubBuilder(None, store)  # type: ignore[arg-type]
    series = hub._timeseries(_QUERY)
    assert [b["count"] for b in series] == [10, 22]


def test_count_tweets_in_window_capped_sparql():
    store = _seed_store()
    _seed_tweets(store)
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]
    n = ctx.count_tweets_in_window(
        _QUERY,
        "2026-07-07T00:00:00+00:00",
        "2026-07-08T00:00:00+00:00",
        limit=2000,
    )
    assert n == 1
    n0 = ctx.count_tweets_in_window(
        _QUERY,
        "2026-07-01T00:00:00+00:00",
        "2026-07-02T00:00:00+00:00",
        limit=2000,
    )
    assert n0 == 0


def test_tweets_returns_rows_with_table_columns():
    store = _seed_store()
    _seed_tweets(store)
    hub = XAppHubBuilder(None, store)  # type: ignore[arg-type]
    # Seeded tweet is on 2026-07-07; hub._tweets uses a rolling 30d window from now,
    # so call tweets_in_window directly for a stable assertion.
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]
    rows = ctx.tweets_in_window(
        _QUERY, "2026-07-07T00:00:00+00:00", "2026-07-08T00:00:00+00:00"
    )
    assert len(rows) == 1
    t = rows[0]
    assert t["text"] == "Big drone sighting near the port"
    assert t["username"] == "dronewatch"
    assert hub._timeseries(_QUERY)  # still reachable via facade


def test_web_loader_references_snapshot_paths():
    web = Path(__file__).resolve().parent / "web"
    loader = (web / "src" / "lib" / "loadSnapshots.ts").read_text(encoding="utf-8")
    page = (web / "src" / "app" / "page.tsx").read_text(encoding="utf-8")
    assert "globals/scenarios.json" in loader
    assert "search_recents_tweets/kpis.json" in loader
    assert "count_recent_tweets/linecharts.json" in loader
    assert "CountPage" in page and "SearchPage" in page
    assert (web / "package.json").is_file()
    assert (web / "next.config.js").is_file()
