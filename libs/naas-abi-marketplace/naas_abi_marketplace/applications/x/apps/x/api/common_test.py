"""Unit tests for the band decomposition and the tweet-page derivation.

Both exist to make a publish read the graph once per concern instead of once per
scenario window, so the tests are all of the same shape: run the cheap path and
the expensive path over the same synthetic data and assert they agree, then
assert how many underlying queries the cheap path actually needed.
"""

from datetime import UTC, datetime, timedelta
from itertools import pairwise
from typing import Any

from naas_abi_marketplace.applications.x.apps.x.api.common import (
    SnapshotContext,
    bands_for_window,
    build_scenarios,
    previous_window,
    scenario_bands,
    slugify,
)

NOW = datetime(2026, 8, 12, 7, 0, tzinfo=UTC)
SCENARIOS = build_scenarios(NOW)
END = SCENARIOS[0]["end_time"]


def _at(hours_ago: float) -> str:
    return (NOW - timedelta(hours=hours_ago)).isoformat()


# --------------------------------------------------------------------------
# Band decomposition
# --------------------------------------------------------------------------


def test_bands_tile_the_whole_range_without_gaps():
    bands = scenario_bands(SCENARIOS)
    # Newest first, and each band's start is the previous band's end.
    for newer, older in pairwise(bands):
        assert newer[0] == older[1]
    assert bands[0][1] == END


def test_every_scenario_window_and_its_previous_period_is_band_aligned():
    bands = scenario_bands(SCENARIOS)
    for scenario in SCENARIOS:
        start, end = scenario["start_time"], scenario["end_time"]
        assert bands_for_window(bands, start, end) is not None
        assert bands_for_window(bands, *previous_window(start, end)) is not None


def test_current_windows_stay_aligned_without_the_previous_period_edges():
    bands = scenario_bands(SCENARIOS, include_previous=False)
    assert len(bands) == len(SCENARIOS)
    for scenario in SCENARIOS:
        indices = bands_for_window(bands, scenario["start_time"], scenario["end_time"])
        assert indices is not None
        # Nested windows all share ``end``, so each one is a prefix of the bands.
        assert indices == list(range(len(indices)))


def test_an_unaligned_window_is_rejected_rather_than_mis_summed():
    """The caller falls back to a direct query — better than a silent undercount."""
    bands = scenario_bands(SCENARIOS)
    assert bands_for_window(bands, _at(30), END) is None
    assert bands_for_window(bands, _at(24), _at(3)) is None


class _BandedCountContext(SnapshotContext):
    """Serves banded counts out of a synthetic tweet list."""

    def __init__(self, created_at: list[str]) -> None:
        super().__init__(None, None, queries=[], scenarios=SCENARIOS)  # type: ignore[arg-type]
        self.created_at = created_at
        self.queries_run = 0

    def _query_banded_post_counts(
        self, query_string: str, *, referenced: bool
    ) -> dict[int, int]:
        self.queries_run += 1
        counts: dict[int, int] = {}
        for moment in self.created_at:
            index = self._band_of(moment)
            if index is not None:
                counts[index] = counts.get(index, 0) + 1
        return counts

    def _band_of(self, moment: str) -> int | None:
        when = datetime.fromisoformat(moment)
        for index, (start, end) in enumerate(self.bands):
            if datetime.fromisoformat(start) <= when < datetime.fromisoformat(end):
                return index
        return None


def test_banded_counts_match_a_direct_count_for_every_window():
    created = [_at(h) for h in (0.5, 3, 20, 25, 40, 70, 100, 200, 400, 900, 1300)]
    ctx = _BandedCountContext(created)

    for scenario in SCENARIOS:
        for start, end in (
            (scenario["start_time"], scenario["end_time"]),
            previous_window(scenario["start_time"], scenario["end_time"]),
        ):
            expected = sum(
                1
                for moment in created
                if datetime.fromisoformat(start)
                <= datetime.fromisoformat(moment)
                < datetime.fromisoformat(end)
            )
            assert (
                ctx.banded_count_for_window("q", start, end, referenced=False)
                == expected
            )

    # 8 windows, one scan — and it is memoized, so a second pass adds nothing.
    assert ctx.queries_run == 1


def test_banded_facet_rollup_sums_the_bands_and_ranks_by_count():
    class _FacetContext(SnapshotContext):
        def __init__(self) -> None:
            super().__init__(None, None, queries=[], scenarios=SCENARIOS)  # type: ignore[arg-type]
            self.queries_run = 0

        def _query_banded_facet_values(
            self, query_string: str, column: str
        ) -> dict[int, dict[str, int]]:
            self.queries_run += 1
            # band 0 = last 24h, band 1 = 24-48h, band 2 = 48h-7d, band 3 = 7d-30d
            return {
                0: {"alice": 3, "bob": 1},
                1: {"alice": 2, "carol": 5},
                2: {"bob": 4},
                3: {"dave": 100},
            }

    ctx = _FacetContext()
    by_id = {s["id"]: s for s in SCENARIOS}

    day = ctx.facet_values_for_window(
        "q", by_id["24h"]["start_time"], by_id["24h"]["end_time"], "username"
    )
    assert day == [{"value": "alice", "count": 3}, {"value": "bob", "count": 1}]

    week = ctx.facet_values_for_window(
        "q", by_id["7d"]["start_time"], by_id["7d"]["end_time"], "username"
    )
    assert week == [
        {"value": "alice", "count": 5},
        {"value": "bob", "count": 5},
        {"value": "carol", "count": 5},
    ]
    # Equal counts are ordered by value so the published file is stable run to run.
    assert [row["value"] for row in week] == sorted(row["value"] for row in week)

    month = ctx.facet_values_for_window(
        "q", by_id["30d"]["start_time"], by_id["30d"]["end_time"], "username"
    )
    assert month[0] == {"value": "dave", "count": 100}

    # One scan served all three windows.
    assert ctx.queries_run == 1


def test_facet_values_differing_only_in_whitespace_are_merged():
    """`user_location` really does hold both "USA" and "USA " in the graph.

    They render as two identical checkboxes splitting one place's count, so the
    rollup folds them together — and the cap is applied after the merge, not
    before, so a variant ranked below it is still counted.
    """

    class _WhitespaceContext(SnapshotContext):
        def __init__(self) -> None:
            super().__init__(None, None, queries=[], scenarios=SCENARIOS)  # type: ignore[arg-type]

        def _query_banded_facet_values(
            self, query_string: str, column: str
        ) -> dict[int, dict[str, int]]:
            return {0: {"USA": 145, "USA ": 5, " USA": 4, "India": 103}}

    ctx = _WhitespaceContext()
    by_id = {s["id"]: s for s in SCENARIOS}
    values = ctx.facet_values_for_window(
        "q", by_id["24h"]["start_time"], by_id["24h"]["end_time"], "location"
    )
    assert values == [
        {"value": "USA", "count": 154},
        {"value": "India", "count": 103},
    ]


def test_facet_rollup_honours_the_value_cap():
    class _ManyValuesContext(SnapshotContext):
        def __init__(self) -> None:
            super().__init__(None, None, queries=[], scenarios=SCENARIOS)  # type: ignore[arg-type]

        def _query_banded_facet_values(
            self, query_string: str, column: str
        ) -> dict[int, dict[str, int]]:
            return {0: {f"user{i:03d}": i for i in range(50)}}

    ctx = _ManyValuesContext()
    by_id = {s["id"]: s for s in SCENARIOS}
    values = ctx.facet_values_for_window(
        "q",
        by_id["24h"]["start_time"],
        by_id["24h"]["end_time"],
        "username",
        limit=10,
    )
    assert len(values) == 10
    assert values[0] == {"value": "user049", "count": 49}


# --------------------------------------------------------------------------
# Tweet-page derivation
# --------------------------------------------------------------------------


class _PagingContext(SnapshotContext):
    """Serves tweet pages out of a synthetic, newest-first tweet list."""

    def __init__(self, created_at: list[str], tweet_limit: int = 1000) -> None:
        super().__init__(
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            queries=[],
            scenarios=SCENARIOS,
            tweet_limit=tweet_limit,
        )
        self.tweets = [
            {"created_at": moment, "username": f"u{i}"}
            for i, moment in enumerate(sorted(created_at, reverse=True))
        ]
        self.windows_queried: list[tuple[str, str]] = []

    def _search_tweets(
        self,
        query_string: str,
        start_time: str,
        end_time: str,
        active: dict[str, dict[str, Any]],
        cap: int,
    ) -> list[dict[str, Any]]:
        self.windows_queried.append((start_time, end_time))
        start = datetime.fromisoformat(start_time)
        end = datetime.fromisoformat(end_time)
        matched = [
            row
            for row in self.tweets
            if start <= datetime.fromisoformat(row["created_at"]) < end
        ]
        return matched[:cap]


def _direct(ctx: _PagingContext, start: str, end: str, cap: int) -> list[dict]:
    """What the window would return if it were queried on its own.

    Reimplemented rather than routed through the context, so asserting on it
    never disturbs ``windows_queried``.
    """
    lower = datetime.fromisoformat(start)
    upper = datetime.fromisoformat(end)
    matched = [
        row
        for row in ctx.tweets
        if lower <= datetime.fromisoformat(row["created_at"]) < upper
    ]
    return matched[:cap]


def test_one_scan_serves_every_current_window_when_the_page_stays_recent():
    """The real shape of this data: far more than `cap` posts inside 24 h."""
    created = [_at(h / 10) for h in range(1, 400)]  # 399 posts in the last 40 h
    ctx = _PagingContext(created, tweet_limit=50)

    results = {
        s["id"]: ctx.tweets_in_window("q", s["start_time"], s["end_time"])
        for s in SCENARIOS
    }

    # Only the narrowest window was actually queried.
    assert ctx.windows_queried == [(SCENARIOS[0]["start_time"], END)]
    # …and every window got exactly what a direct query would have returned.
    for scenario in SCENARIOS:
        assert results[scenario["id"]] == _direct(
            ctx, scenario["start_time"], scenario["end_time"], 50
        )


def test_a_page_that_reaches_its_own_edge_does_not_serve_wider_windows():
    """Fewer posts than `cap` in 24 h — the wider windows hold strictly more."""
    created = [_at(2), _at(5), _at(30), _at(100), _at(500)]
    ctx = _PagingContext(created, tweet_limit=50)

    results = {
        s["id"]: ctx.tweets_in_window("q", s["start_time"], s["end_time"])
        for s in SCENARIOS
    }

    assert len(ctx.windows_queried) == len(SCENARIOS)
    for scenario in SCENARIOS:
        assert results[scenario["id"]] == _direct(
            ctx, scenario["start_time"], scenario["end_time"], 50
        )
    # Sanity: the windows really do differ, so the assertion above has teeth.
    assert len(results["24h"]) == 2
    assert len(results["30d"]) == 5


def test_a_full_page_ending_at_the_window_edge_is_not_reused():
    """Guard the boundary: `cap` posts whose oldest sits exactly on the start.

    Widening could legitimately pull in older posts, so reusing the page here
    would be a guess — the wider window must be queried.
    """
    start_24h = SCENARIOS[0]["start_time"]
    created = [start_24h, _at(2), _at(1), _at(100)]
    ctx = _PagingContext(created, tweet_limit=3)

    day = ctx.tweets_in_window("q", start_24h, END)
    assert len(day) == 3

    month = ctx.tweets_in_window(
        "q", SCENARIOS[3]["start_time"], SCENARIOS[3]["end_time"]
    )
    assert len(ctx.windows_queried) == 2
    assert month == _direct(
        ctx, SCENARIOS[3]["start_time"], SCENARIOS[3]["end_time"], 3
    )


def test_a_wider_page_is_filtered_down_to_a_narrower_window():
    """Visiting widest-first still costs one scan, via the filter rule."""
    created = [_at(h) for h in (1, 10, 30, 60, 200, 600)]
    ctx = _PagingContext(created, tweet_limit=50)

    for scenario in reversed(SCENARIOS):
        result = ctx.tweets_in_window("q", scenario["start_time"], scenario["end_time"])
        assert result == _direct(ctx, scenario["start_time"], scenario["end_time"], 50)

    assert ctx.windows_queried == [(SCENARIOS[3]["start_time"], END)]


def test_previous_windows_are_not_derived_from_current_ones():
    """They end at a different instant, so no page of theirs is comparable."""
    created = [_at(h) for h in (1, 30, 40, 60)]
    ctx = _PagingContext(created, tweet_limit=50)

    scenario = SCENARIOS[0]
    ctx.tweets_in_window("q", scenario["start_time"], scenario["end_time"])
    prev_start, prev_end = previous_window(scenario["start_time"], scenario["end_time"])
    result = ctx.tweets_in_window("q", prev_start, prev_end)

    assert (prev_start, prev_end) in ctx.windows_queried
    assert result == _direct(ctx, prev_start, prev_end, 50)


def test_filtered_reads_are_never_served_from_an_unfiltered_page():
    created = [_at(h) for h in (1, 2, 3)]
    ctx = _PagingContext(created, tweet_limit=50)

    scenario = SCENARIOS[0]
    ctx.tweets_in_window("q", scenario["start_time"], scenario["end_time"])
    before = len(ctx.windows_queried)
    ctx.search_tweets(
        "q",
        scenario["start_time"],
        scenario["end_time"],
        filters={"username": {"contains": "u1"}},
    )
    assert len(ctx.windows_queried) == before + 1


# --------------------------------------------------------------------------
# Projection routing
# --------------------------------------------------------------------------
#
# Same shape as above: the projection is the cheap path and the graph is the
# expensive one, so each test asserts both what came back and that the graph was
# left alone — or, for the fallback cases, that it was not.


QUERY = "(drone OR drones) lang:en"
QUERY_SLUG = slugify(QUERY)


class _FakeCache:
    """Stands in for :class:`CacheReader`, recording what was asked of it."""

    def __init__(self, slugs: set[str] | None = None) -> None:
        self.slugs = {QUERY_SLUG} if slugs is None else slugs
        self.slug_reads = 0
        self.calls: list[tuple] = []

    def known_query_slugs(self) -> set[str]:
        self.slug_reads += 1
        return self.slugs

    def count_in_window(self, start, end, *, referenced=False, query_slug=None) -> int:
        self.calls.append(("count", start, end, referenced, query_slug))
        return 7 if not referenced else 3

    def facet_values(self, start, end, column, *, limit=500, query_slug=None) -> list:
        self.calls.append(("facets", start, end, column, query_slug))
        return [{"value": "USA", "count": 4}]

    def newest_posts(self, start, end, *, limit=1000, query_slug=None) -> list:
        self.calls.append(("tweets", start, end, limit, query_slug))
        return [{"created_at": end, "text": "from the projection", "username": "alice"}]


class _RoutingContext(SnapshotContext):
    """Counts every read that reached the graph."""

    def __init__(self, cache: _FakeCache | None) -> None:
        super().__init__(
            None,  # type: ignore[arg-type]
            None,  # type: ignore[arg-type]
            queries=[],
            scenarios=SCENARIOS,
            cache=cache,
        )
        self.graph_reads = 0

    def _query_banded_post_counts(self, query_string, *, referenced) -> dict[int, int]:
        self.graph_reads += 1
        return {0: 1}

    def _query_banded_facet_values(self, query_string, column) -> dict:
        self.graph_reads += 1
        return {0: {"from-the-graph": 1}}

    def _search_tweets(self, query_string, start_time, end_time, active, cap) -> list:
        self.graph_reads += 1
        return [{"created_at": end_time, "text": "from the graph", "username": "bob"}]


def _window() -> tuple[str, str]:
    return SCENARIOS[0]["start_time"], SCENARIOS[0]["end_time"]


def test_a_covered_query_is_answered_without_touching_the_graph():
    cache = _FakeCache()
    ctx = _RoutingContext(cache)
    start, end = _window()

    assert ctx.banded_count_for_window(QUERY, start, end, referenced=False) == 7
    assert ctx.banded_count_for_window(QUERY, start, end, referenced=True) == 3
    assert ctx.facet_values_for_window(QUERY, start, end, "location") == [
        {"value": "USA", "count": 4}
    ]
    assert ctx.tweets_in_window(QUERY, start, end)[0]["text"] == "from the projection"

    assert ctx.graph_reads == 0
    # Every read was scoped to the query, not left to span the whole projection.
    assert all(call[-1] == QUERY_SLUG for call in cache.calls)


def test_a_query_the_projection_does_not_cover_falls_back_to_the_graph():
    """A renamed query still has its history in the graph; publish that, not zero."""
    cache = _FakeCache(slugs={"some_other_query"})
    ctx = _RoutingContext(cache)
    start, end = _window()

    assert ctx.banded_count_for_window(QUERY, start, end, referenced=False) == 1
    assert ctx.tweets_in_window(QUERY, start, end)[0]["text"] == "from the graph"
    assert ctx.facet_values_for_window(QUERY, start, end, "location") == [
        {"value": "from-the-graph", "count": 1}
    ]

    assert ctx.graph_reads == 3
    assert cache.calls == []


def test_a_filtered_tweet_read_stays_on_the_graph():
    """Filters are pushed into SPARQL so a search sees more than a capped page."""
    cache = _FakeCache()
    ctx = _RoutingContext(cache)
    start, end = _window()

    rows = ctx.search_tweets(
        QUERY, start, end, filters={"username": {"contains": "ali"}}
    )

    assert rows[0]["text"] == "from the graph"
    assert ctx.graph_reads == 1
    assert cache.calls == []


def test_without_a_projection_every_read_goes_to_the_graph():
    ctx = _RoutingContext(None)
    start, end = _window()

    ctx.banded_count_for_window(QUERY, start, end, referenced=False)
    ctx.tweets_in_window(QUERY, start, end)

    assert ctx.graph_reads == 2


def test_the_covered_slug_set_is_read_once_per_publish():
    """It is a scan of the projection; the pages ask for many windows each."""
    cache = _FakeCache()
    ctx = _RoutingContext(cache)
    start, end = _window()

    for scenario in SCENARIOS:
        ctx.banded_count_for_window(
            QUERY, scenario["start_time"], scenario["end_time"], referenced=False
        )
        ctx.tweets_in_window(QUERY, scenario["start_time"], scenario["end_time"])
    ctx.facet_values_for_window(QUERY, start, end, "location")

    assert cache.slug_reads == 1
