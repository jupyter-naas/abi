"""Unit tests for the X post-count app hub (slugify, render, timeseries SPARQL).

The timeseries test runs the hub's real SPARQL against an rdflib-backed fake
triple store loaded with the exact graph shape XCountRecentTweetsPipeline emits,
so it doubles as a check of the ontology↔SPARQL contract.
"""

from datetime import UTC, datetime

from rdflib import RDF, Dataset, Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

from naas_abi_marketplace.applications.x.apps.x.hub import (
    XCountAppHubBuilder,
    render_index,
    slugify,
)
from naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcessOntology import (
    CountInterval,
    TweetCountBucket,
    TweetCountResultSet,
)

_NS = "http://ontology.naas.ai/x/"
_GRAPH = "http://ontology.naas.ai/graph/x_recent_posts_count"
_TWEET_GRAPH = "http://ontology.naas.ai/graph/x"
_QUERY = "(drone OR uas) lang:en -is:retweet"
_X = Namespace(_NS)


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


def _seed_tweets(store: "_FakeTripleStore") -> None:
    """Add one tweet (with author) linked to _QUERY into the tweet graph."""
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


def test_tweets_returns_rows_with_table_columns():
    store = _seed_store()
    _seed_tweets(store)
    hub = XCountAppHubBuilder(None, store)  # type: ignore[arg-type]
    rows = hub._tweets(_QUERY)
    assert len(rows) == 1
    t = rows[0]
    assert t["text"] == "Big drone sighting near the port"
    assert t["url"] == "https://x.com/9/status/1"
    assert t["username"] == "dronewatch"
    assert t["location"] == "Ankara"
    assert t["verified_type"] == "blue"
    assert t["created_at"].startswith("2026-07-07T13:30:00")


def test_tweets_unknown_query_is_empty():
    store = _seed_store()
    _seed_tweets(store)
    hub = XCountAppHubBuilder(None, store)  # type: ignore[arg-type]
    assert hub._tweets("nothing matching here") == []


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
    html = render_index(series, datetime(2026, 7, 7, 14, 0, tzinfo=UTC))
    assert "<!doctype html>" in html
    assert "__DATA_JSON__" not in html and "__BUILT_AT__" not in html
    # Renamed app + X theme + both dropdowns + KPI labels present.
    assert "Recent Tweets" in html
    assert "#1d9bf0" in html and "Last 24 hours" in html and "Last 30 days" in html
    # Scenario filter + High/Low KPIs (renamed from Time range / Peak / Lowest).
    assert "Scenario" in html and ">High<" in html and ">Low<" in html
    # Timezone filter (display-only): UTC default + CET / EST / PST.
    assert 'id="tz-select"' in html and "Timezone" in html
    assert 'value="Europe/Paris"' in html and 'value="America/New_York"' in html
    assert 'value="America/Los_Angeles"' in html
    assert "timeZone: tz" in html
    # Real query embedded (dropdown shows the query, not the label).
    assert _QUERY in html
    # Border radius removed everywhere.
    assert "border-radius: 0" in html and "9999px" not in html
    # Three sections: chart, tweets table, author ranking.
    assert "Tweets in range" in html and "Top authors" in html
    assert 'id="tweets-table"' in html and 'id="authors-table"' in html
    # Excel-like data table (createDataTable + 50-row pagination + fetch).
    assert "createDataTable" in html
    assert "Location" in html and "Verified" in html
    assert "_tweets.json" in html
    assert "PAGE_SIZE = 50" in html
    # Sidebar navigation: brand + two pages (Count / Search) + collapse toggle.
    assert 'class="sidebar"' in html and 'id="sidebar-toggle"' in html
    assert "X / Twitter" in html
    assert 'data-page="count"' in html and 'data-page="search"' in html
    assert "nav-tip" in html and "showPage" in html
    # Topnav page title, uppercased via CSS.
    assert 'id="page-title"' in html and "text-transform: uppercase" in html
    # Two pages: Count Recent Tweets (counts) + Search Recent Tweets.
    assert "Count Recent Tweets" in html and "Search Recent Tweets" in html
    assert 'id="page-count"' in html and 'id="page-search"' in html
    # Search section KPIs: Total Tweets Ingested (comp) + Coverage % (comp in pts)
    # + a replicated Total Tweets (count-endpoint total, coverage denominator).
    assert "Total Tweets Ingested" in html and "Coverage" in html
    assert 'id="kpi-ingested"' in html and 'id="kpi-coverage"' in html
    assert 'id="kpi-stotal"' in html and 'class="kpis three"' in html
    assert "setSearchKpis" in html and '" pts"' in html
    # Count KPI relabelled Total posts → Total Tweets.
    assert ">Total Tweets<" in html and ">Total posts<" not in html
    # Posts over time chart legend (Current vs Previous period).
    assert "chart-legend" in html and "Previous period" in html
    assert 'id="legend-prev"' in html
    # Bar-chart KPIs: top authors + top author locations (scrollable), moved into
    # the Search section below "Posts over time".
    assert "Top authors" in html and "Top author locations" in html
    assert 'id="bars-authors"' in html and 'id="bars-locations"' in html
    assert "renderBarList" in html and "authorLocationRanking" in html
    assert html.index("Posts over time") < html.index('id="bars-authors"')
    # High/Low hints show the interval (start – end), not just the start.
    assert "rangeLabel" in html
    # Comparison ("previous period") scenario: KPI deltas, chart overlay, bar deltas.
    assert "aggregateRange" in html and "kpi-delta" in html
    assert "prev. period" in html and "current vs previous period" in html
    assert "compFrom" in html and "compTweets" in html
