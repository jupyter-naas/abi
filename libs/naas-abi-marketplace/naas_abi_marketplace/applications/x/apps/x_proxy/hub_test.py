"""Unit tests for the X Recent Tweets app hub + api SPARQL helpers."""

from datetime import UTC, datetime
from pathlib import Path

from naas_abi_marketplace.applications.x.apps.x_proxy.api.common import (
    SnapshotContext,
    build_scenarios,
    extrapolate_partial_hour,
    normalize_tweet_filters,
    slugify,
)
from naas_abi_marketplace.applications.x.apps.x_proxy.hub import XAppHubBuilder
from naas_abi_marketplace.applications.x.ontologies.processes.XCountRecentTweetsProcess import (
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


def _seed_tweet(
    store: "_FakeTripleStore",
    *,
    index: int,
    created: str,
    text: str,
    username: str,
    location: str,
    verified: str = "none",
) -> None:
    """Add one more tweet to the existing search query / result set."""
    g = Graph()
    sq, proc, rs = (
        _X["SearchQuery/q1"],
        _X["SearchRecentTweets/p1"],
        _X["SearchResultSet/r1"],
    )
    tw, au = _X[f"Tweet/{index}"], _X[f"XUser/{username}"]
    g.add((sq, RDF.type, _X.SearchQuery))
    g.add((sq, _X.query_string, Literal(_QUERY)))
    g.add((proc, RDF.type, _X.SearchRecentTweets))
    g.add((proc, _X.usesSearchQuery, sq))
    g.add((proc, _X.producesSearchResult, rs))
    g.add((tw, RDF.type, _X.Tweet))
    g.add((tw, _X.isContainedInSearchResultSet, rs))
    g.add((tw, _X.tweet_created_at, Literal(created, datatype=XSD.dateTime)))
    g.add((tw, _X.full_text, Literal(text)))
    g.add((tw, _X.url, Literal(f"https://x.com/{username}/status/{index}")))
    g.add((tw, _X.isAuthoredBy, au))
    g.add((au, _X.username, Literal(username)))
    g.add((au, _X.user_location, Literal(location)))
    g.add((au, _X.verified_type, Literal(verified)))
    store.insert_graph(g, _TWEET_GRAPH)


def _seed_tweet_corpus() -> "_FakeTripleStore":
    """Store with four tweets spanning two authors / locations / keywords."""
    store = _seed_store()
    _seed_tweets(store)  # drone / dronewatch / Ankara / blue @ 13:30
    _seed_tweet(
        store,
        index=2,
        created="2026-07-07T14:00:00+00:00",
        text="Another drones report over the airfield",
        username="uasnews",
        location="Kyiv",
    )
    _seed_tweet(
        store,
        index=3,
        created="2026-07-07T15:00:00+00:00",
        text="Unrelated chatter about the weather",
        username="uasnews",
        location="Kyiv",
    )
    _seed_tweet(
        store,
        index=4,
        created="2026-07-07T16:00:00+00:00",
        text="Drones everywhere this morning",
        username="skywatch",
        location="Ankara",
    )
    return store


_WINDOW = ("2026-07-07T00:00:00+00:00", "2026-07-08T00:00:00+00:00")


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


def test_build_scenarios_floors_both_edges_to_the_clock_hour():
    """An unaligned publish time must not shift the window off the hour grid."""
    scenarios = build_scenarios(datetime(2026, 7, 28, 13, 2, 22, 135321, tzinfo=UTC))
    day = next(s for s in scenarios if s["id"] == "24h")
    assert day["end_time"] == "2026-07-28T13:00:00+00:00"
    assert day["start_time"] == "2026-07-27T13:00:00+00:00"
    for s in scenarios:
        for edge in ("start_time", "end_time"):
            parsed = datetime.fromisoformat(s[edge])
            assert (parsed.minute, parsed.second, parsed.microsecond) == (0, 0, 0)


def test_aggregate_buckets_keeps_the_first_bucket_of_an_aligned_window():
    """The head bucket was dropped whole when the window started mid-hour."""
    ctx = SnapshotContext(None, _seed_store(), queries=[])  # type: ignore[arg-type]
    buckets = ctx.timeseries(_QUERY)  # 12:00 and 13:00 on 2026-07-07
    aligned = ctx.aggregate_buckets(
        buckets,
        "2026-07-07T12:00:00+00:00",
        "2026-07-07T14:00:00+00:00",
        daily=False,
    )
    assert [p["value"] for p in aligned] == [10, 22]

    # Two minutes past the hour is enough to lose the 12:00 bucket entirely.
    unaligned = ctx.aggregate_buckets(
        buckets,
        "2026-07-07T12:02:22+00:00",
        "2026-07-07T14:02:22+00:00",
        daily=False,
    )
    assert [p["value"] for p in unaligned] == [22]


def test_timeseries_returns_sorted_hourly_buckets():
    store = _seed_store()
    hub = XAppHubBuilder(None, store)  # type: ignore[arg-type]
    series = hub._timeseries(_QUERY)
    assert [b["count"] for b in series] == [10, 22]


def test_count_tweets_in_window_capped_and_uncapped_sparql():
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
    n_uncapped = ctx.count_tweets_in_window(
        _QUERY,
        "2026-07-07T00:00:00+00:00",
        "2026-07-08T00:00:00+00:00",
        limit=0,
    )
    assert n_uncapped == 1
    n0 = ctx.count_tweets_in_window(
        _QUERY,
        "2026-07-01T00:00:00+00:00",
        "2026-07-02T00:00:00+00:00",
        limit=0,
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


def test_ingested_timeseries_buckets_matched_tweets_by_created_hour():
    """Search line chart: counts per created_at hour, not a running total."""
    store = _seed_store()
    _seed_tweets(store)
    _seed_tweet(
        store,
        index=2,
        created="2026-07-07T13:45:00+00:00",
        text="Second drone in the same hour",
        username="dronewatch",
        location="Ankara",
    )
    _seed_tweet(
        store,
        index=3,
        created="2026-07-07T14:10:00+00:00",
        text="Next hour",
        username="uasnews",
        location="Kyiv",
    )
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]
    buckets = ctx.ingested_timeseries(
        _QUERY, "2026-07-07T13:00:00+00:00", "2026-07-07T15:00:00+00:00"
    )
    assert [b["count"] for b in buckets] == [2, 1]
    assert datetime.fromisoformat(buckets[0]["start"]).hour == 13
    assert datetime.fromisoformat(buckets[1]["start"]).hour == 14


def test_search_tweets_text_contains_scans_whole_window():
    """A keyword search returns every matching tweet, newest first."""
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    rows = ctx.search_tweets(_QUERY, *_WINDOW, filters={"text": {"contains": "drone"}})
    assert [r["username"] for r in rows] == ["skywatch", "uasnews", "dronewatch"]
    assert all("drone" in r["text"].lower() for r in rows)


def test_search_tweets_text_contains_is_case_insensitive():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    lower = ctx.search_tweets(
        _QUERY, *_WINDOW, filters={"text": {"contains": "drones"}}
    )
    upper = ctx.search_tweets(
        _QUERY, *_WINDOW, filters={"text": {"contains": "DRONES"}}
    )
    assert len(lower) == 2
    assert [r["url"] for r in lower] == [r["url"] for r in upper]


def test_search_tweets_value_set_matches_any_selected_value():
    """Checkbox selections OR within a column."""
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    rows = ctx.search_tweets(
        _QUERY, *_WINDOW, filters={"username": {"values": ["uasnews", "skywatch"]}}
    )
    assert sorted({r["username"] for r in rows}) == ["skywatch", "uasnews"]
    assert len(rows) == 3


def test_search_tweets_ands_across_columns():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    rows = ctx.search_tweets(
        _QUERY,
        *_WINDOW,
        filters={
            "text": {"contains": "drone"},
            "location": {"values": ["Ankara"]},
        },
    )
    assert sorted(r["username"] for r in rows) == ["dronewatch", "skywatch"]


def test_search_tweets_limit_applies_after_filtering():
    """The cap selects the newest *matching* tweets, not matches within a cap."""
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    rows = ctx.search_tweets(
        _QUERY, *_WINDOW, filters={"text": {"contains": "drone"}}, limit=2
    )
    assert [r["username"] for r in rows] == ["skywatch", "uasnews"]


def test_search_tweets_without_filters_matches_tweets_in_window():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    assert ctx.search_tweets(_QUERY, *_WINDOW) == ctx.tweets_in_window(_QUERY, *_WINDOW)


def test_search_tweets_escapes_quotes_in_filter_values():
    """A quote in a filter must not break out of the SPARQL string literal."""
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    rows = ctx.search_tweets(
        _QUERY, *_WINDOW, filters={"text": {"contains": '") } UNION { ?s ?p ?o . #'}}
    )
    assert rows == []


def test_distinct_column_values_counts_and_ranks():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    values = ctx.distinct_column_values(_QUERY, *_WINDOW, "username")
    assert [v["value"] for v in values] == ["uasnews", "dronewatch", "skywatch"] or [
        v["value"] for v in values
    ] == ["uasnews", "skywatch", "dronewatch"]
    assert {v["value"]: v["count"] for v in values}["uasnews"] == 2


def test_distinct_column_values_honours_other_column_filters():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    values = ctx.distinct_column_values(
        _QUERY, *_WINDOW, "username", filters={"location": {"values": ["Ankara"]}}
    )
    assert sorted(v["value"] for v in values) == ["dronewatch", "skywatch"]


def test_distinct_column_values_ignores_its_own_column_filter():
    """Ticking one box must not collapse the column's own option list."""
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    values = ctx.distinct_column_values(
        _QUERY, *_WINDOW, "username", filters={"username": {"values": ["skywatch"]}}
    )
    assert sorted(v["value"] for v in values) == ["dronewatch", "skywatch", "uasnews"]


def test_distinct_column_values_search_narrows_options():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    values = ctx.distinct_column_values(_QUERY, *_WINDOW, "username", contains="watch")
    assert sorted(v["value"] for v in values) == ["dronewatch", "skywatch"]


def test_distinct_column_values_rejects_unknown_column():
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    assert ctx.distinct_column_values(_QUERY, *_WINDOW, "; DROP") == []


def test_normalize_tweet_filters_drops_unknown_and_empty():
    normalized = normalize_tweet_filters(
        {
            "text": {"contains": " drone "},
            "username": {"values": ["a"]},
            "location": {"contains": "", "values": []},
            "evil": {"contains": "x"},
            "url": "not-a-dict",
        }
    )
    assert set(normalized) == {"text", "username"}
    assert normalized["text"]["contains"] == "drone"
    assert normalized["username"]["values"] == ["a"]


def test_web_loader_references_snapshot_paths():
    web = Path(__file__).resolve().parent / "web"
    loader = (web / "src" / "lib" / "loadSnapshots.ts").read_text(encoding="utf-8")
    view = (web / "src" / "components" / "AppView.tsx").read_text(encoding="utf-8")
    assert "globals/scenarios.json" in loader
    assert "search_recents_tweets/kpis.json" in loader
    assert "count_recent_tweets/linecharts.json" in loader
    assert "CountPage" in view and "SearchPage" in view
    assert (web / "package.json").is_file()
    assert (web / "next.config.js").is_file()


def test_every_page_has_a_route():
    """Every page ``config.yaml`` names must have a route to export.

    The paths live in the config now (`app_config.py` compiles them into
    `lib/appConfig.generated.ts`), so this asserts the app the config describes
    is the app on disk. Users is unslashed so its URL is ``search?user=``, not
    ``search/?user=``.
    """
    from naas_abi_marketplace.applications.x.apps.x_proxy.app_config import (
        load_config,
    )

    web = Path(__file__).resolve().parent / "web"
    paths = {page.key: page.path for page in load_config().pages}
    assert paths == {
        "search": "/posts/search-posts-recent/",
        "count": "/posts/get-posts-counts-recent/",
        "users": "/users/search",
        "parameters": "/parameters/",
    }
    for path in paths.values():
        assert (web / "src" / "app" / path.strip("/") / "page.tsx").is_file(), path


# ----- in-progress hour extrapolation ---------------------------------------

_J1_BUCKETS = [
    {
        "start": "2026-07-06T15:00:00+00:00",
        "end": "2026-07-06T16:00:00+00:00",
        "count": 300,
    },
    {
        "start": "2026-07-07T14:00:00+00:00",
        "end": "2026-07-07T15:00:00+00:00",
        "count": 280,
    },
]


def test_extrapolate_partial_hour_prorates_yesterdays_same_hour():
    """15:25 → 35 minutes missing → 300 * 35/60 = 175 added to the observed."""
    partial = {
        "start": "2026-07-07T15:00:00+00:00",
        "end": "2026-07-07T15:25:00+00:00",
        "count": 120,
    }
    out = extrapolate_partial_hour(partial, _J1_BUCKETS)
    assert out["missing_minutes"] == 35
    assert out["estimated_value"] == 175
    assert out["observed"] == 120
    assert out["value"] == 295


def test_extrapolate_partial_hour_keeps_observed_traceable():
    """The folded value must still be decomposable for an audit."""
    partial = {
        "start": "2026-07-07T15:00:00+00:00",
        "end": "2026-07-07T15:25:00+00:00",
        "count": 120,
    }
    out = extrapolate_partial_hour(partial, _J1_BUCKETS)
    assert out["value"] == out["observed"] + out["estimated_value"]


def test_extrapolate_partial_hour_without_yesterday_does_not_invent_a_number():
    partial = {
        "start": "2026-07-07T15:00:00+00:00",
        "end": "2026-07-07T15:25:00+00:00",
        "count": 120,
    }
    out = extrapolate_partial_hour(partial, [])
    assert out["estimated_value"] == 0
    assert out["value"] == 120


def test_extrapolate_partial_hour_adds_nothing_once_the_hour_is_complete():
    partial = {
        "start": "2026-07-07T15:00:00+00:00",
        "end": "2026-07-07T16:00:00+00:00",
        "count": 310,
    }
    out = extrapolate_partial_hour(partial, _J1_BUCKETS)
    assert out["missing_minutes"] == 0
    assert out["estimated_value"] == 0
    assert out["value"] == 310


def test_extrapolate_partial_hour_returns_none_without_a_partial():
    assert extrapolate_partial_hour(None, _J1_BUCKETS) is None
    assert extrapolate_partial_hour({"start": "nope"}, _J1_BUCKETS) is None


def _seed_count_buckets(store: "_FakeTripleStore") -> None:
    """A complete 14:00 hour plus an in-progress 15:00 partial slot."""
    g = Graph()
    rs = _X["TweetCountResultSet/rs1"]
    g.add((rs, RDF.type, _X.TweetCountResultSet))
    g.add((rs, _X.query_string, Literal(_QUERY)))
    for stable_id, start, end, count in (
        (
            "drones-2026-07-07T14:00:00+00:00",
            "2026-07-07T14:00:00+00:00",
            "2026-07-07T15:00:00+00:00",
            280,
        ),
        (
            "drones-partial",
            "2026-07-07T15:00:00+00:00",
            "2026-07-07T15:25:00+00:00",
            120,
        ),
    ):
        bucket = _X[f"TweetCountBucket/{stable_id}"]
        interval = _X[f"CountInterval/{stable_id}"]
        g.add((rs, _X.containsCountBucket, bucket))
        g.add((bucket, _X.bucket_tweet_count, Literal(count)))
        g.add((bucket, _X.hasCountInterval, interval))
        g.add((interval, _X.bucket_start, Literal(start)))
        g.add((interval, _X.bucket_end, Literal(end)))
    store.insert_graph(g, _GRAPH)


def test_timeseries_excludes_the_in_progress_partial_slot():
    """A partial shares its hour's bucket_start; charting it would double-count."""
    store = _FakeTripleStore()
    _seed_count_buckets(store)
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]
    starts = [b["start"] for b in ctx.timeseries(_QUERY)]
    assert starts == ["2026-07-07T14:00:00+00:00"]


def test_partial_bucket_returns_the_in_progress_slot():
    store = _FakeTripleStore()
    _seed_count_buckets(store)
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]
    partial = ctx.partial_bucket(_QUERY)
    assert partial["start"] == "2026-07-07T15:00:00+00:00"
    assert partial["end"] == "2026-07-07T15:25:00+00:00"
    assert partial["count"] == 120


def test_partial_bucket_is_none_when_only_complete_hours_exist():
    store = _FakeTripleStore()
    g = Graph()
    rs = _X["TweetCountResultSet/rs2"]
    bucket = _X["TweetCountBucket/drones-2026-07-07T14:00:00+00:00"]
    interval = _X["CountInterval/drones-2026-07-07T14:00:00+00:00"]
    g.add((rs, RDF.type, _X.TweetCountResultSet))
    g.add((rs, _X.query_string, Literal(_QUERY)))
    g.add((rs, _X.containsCountBucket, bucket))
    g.add((bucket, _X.bucket_tweet_count, Literal(280)))
    g.add((bucket, _X.hasCountInterval, interval))
    g.add((interval, _X.bucket_start, Literal("2026-07-07T14:00:00+00:00")))
    g.add((interval, _X.bucket_end, Literal("2026-07-07T15:00:00+00:00")))
    store.insert_graph(g, _GRAPH)
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]
    assert ctx.partial_bucket(_QUERY) is None


# ----- per-publish SPARQL memo ---------------------------------------------


class _CountingTripleStore(_FakeTripleStore):
    """Triple store that records how many SPARQL queries it actually ran."""

    def __init__(self) -> None:
        super().__init__()
        self.queries_run = 0

    def query(self, sparql: str):
        self.queries_run += 1
        return super().query(sparql)


def _counting_corpus() -> _CountingTripleStore:
    store = _CountingTripleStore()
    seeded = _seed_tweet_corpus()
    store.dataset = seeded.dataset
    return store


def test_repeated_tweets_in_window_runs_one_query_per_publish():
    """tables / barcharts ask for the same rows — run it once."""
    store = _counting_corpus()
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]

    first = ctx.tweets_in_window(_QUERY, *_WINDOW)
    assert store.queries_run == 1
    for _ in range(4):
        assert ctx.tweets_in_window(_QUERY, *_WINDOW) == first
    assert store.queries_run == 1

    # A different window is a different key and must still hit the graph.
    ctx.tweets_in_window(_QUERY, "2026-07-06T00:00:00+00:00", _WINDOW[0])
    assert store.queries_run == 2


def test_memo_separates_distinct_filters_and_caches_counts():
    store = _counting_corpus()
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]

    ctx.search_tweets(_QUERY, *_WINDOW, filters={"text": {"contains": "drone"}})
    ctx.search_tweets(_QUERY, *_WINDOW, filters={"text": {"contains": "drone"}})
    assert store.queries_run == 1
    # Different filter → different key.
    ctx.search_tweets(_QUERY, *_WINDOW, filters={"text": {"contains": "weather"}})
    assert store.queries_run == 2
    # An empty/absent filter set normalizes to the same key.
    ctx.search_tweets(_QUERY, *_WINDOW, filters={})
    ctx.search_tweets(_QUERY, *_WINDOW, filters=None)
    assert store.queries_run == 3

    before = store.queries_run
    ctx.count_tweets_in_window(_QUERY, *_WINDOW, limit=0)
    ctx.count_tweets_in_window(_QUERY, *_WINDOW, limit=0)
    assert store.queries_run == before + 1


def test_sum_counts_in_window_reuses_one_timeseries_query():
    """Every KPI window re-derives its total from the same bucket list."""
    store = _CountingTripleStore()
    store.dataset = _seed_store().dataset
    ctx = SnapshotContext(None, store, queries=[])  # type: ignore[arg-type]

    ctx.sum_counts_in_window(
        _QUERY, "2026-07-07T12:00:00+00:00", "2026-07-07T13:00:00+00:00"
    )
    ctx.sum_counts_in_window(
        _QUERY, "2026-07-07T13:00:00+00:00", "2026-07-07T14:00:00+00:00"
    )
    ctx.timeseries(_QUERY)
    assert store.queries_run == 1


# ----- lazy-result error handling ------------------------------------------


def test_posts_for_usernames_survives_a_corpus_with_no_media():
    """rdflib raises on an unbound GROUP_CONCAT — this must not kill a publish.

    Regression: the ``fs`` local-dev adapter returns a lazy rdflib Result, so
    the query only evaluated during iteration and ``NotBoundError`` escaped the
    fail-soft handler. No seeded tweet here has ``hasAttachedMedia``.
    """
    ctx = SnapshotContext(None, _seed_tweet_corpus(), queries=[])  # type: ignore[arg-type]
    posts = ctx.posts_for_usernames(["dronewatch", "uasnews"])
    assert sorted(posts) == ["dronewatch", "uasnews"]
    assert [p["text"] for p in posts["dronewatch"]] == [
        "Big drone sighting near the port"
    ]
    # No media anywhere → the key is simply absent.
    assert all("media_url" not in p for ps in posts.values() for p in ps)


def test_posts_for_usernames_keeps_media_urls_clean():
    """A tweet mixing a usable media node with an empty one stays separator-clean."""
    store = _seed_tweet_corpus()
    g = Graph()
    tw = _X["Tweet/2"]
    good, blank = _X["Media/good"], _X["Media/blank"]
    g.add((tw, _X.hasAttachedMedia, good))
    g.add((good, _X.media_url, Literal("https://pbs.x.com/a.jpg")))
    # A media node carrying neither media_url nor preview_image_url.
    g.add((tw, _X.hasAttachedMedia, blank))
    store.insert_graph(g, _TWEET_GRAPH)

    posts = SnapshotContext(None, store, queries=[]).posts_for_usernames(["uasnews"])  # type: ignore[arg-type]
    with_media = [p for p in posts["uasnews"] if "media_url" in p]
    assert len(with_media) == 1
    assert with_media[0]["media_url"] == "https://pbs.x.com/a.jpg"


def test_query_failure_degrades_to_an_empty_section():
    """A broken triple store logs and yields nothing — it never raises."""

    class _Broken:
        def query(self, sparql: str):
            raise RuntimeError("triple store unavailable")

    ctx = SnapshotContext(None, _Broken(), queries=[])  # type: ignore[arg-type]
    assert ctx.all_authors() == []
    assert ctx.timeseries(_QUERY) == []
    assert ctx.search_tweets(_QUERY, *_WINDOW) == []
    assert ctx.count_tweets_in_window(_QUERY, *_WINDOW, limit=0) == 0
    assert ctx.distinct_column_values(_QUERY, *_WINDOW, "username") == []
    assert ctx.posts_for_usernames(["a"]) == {}
    assert ctx.accounts_for_usernames(["a"]) == {}
    assert ctx.partial_bucket(_QUERY) is None


def test_lazily_failing_result_is_caught_like_an_eager_one():
    """The fs adapter fails during iteration, not at query() — catch it anyway."""

    class _LazilyBroken:
        def query(self, sparql: str):
            def _rows():
                yield object()
                raise RuntimeError("evaluated lazily, blew up mid-iteration")

            return _rows()

    ctx = SnapshotContext(None, _LazilyBroken(), queries=[])  # type: ignore[arg-type]
    assert ctx.all_authors() == []
    assert ctx.search_tweets(_QUERY, *_WINDOW) == []
