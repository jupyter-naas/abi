from dataclasses import replace
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.tests import fixtures
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.traces import (
    InvalidTraceQuery,
    ServiceCount,
    Span,
    TraceQuery,
    TraceRoot,
    TraceSummary,
    normalize_trace_id,
    service_counts,
    summarize,
)

NOW = datetime(2026, 10, 2, 9, 0, 0, tzinfo=UTC)


def _summary(duration_ms=100.0, errors=0):
    return TraceSummary("a" * 32, TraceRoot("s", "n"), "", duration_ms, 1, errors, ())


def test_trace_ids_are_32_hex_characters_lowercased():
    assert normalize_trace_id(" 4BF92F3577B34DA6A3CE929D0E0E4736 ") == fixtures.TRACE_B
    for bad in ("", "xyz", "0" * 31, "0" * 33, "g" * 32, "../" + "0" * 29):
        with pytest.raises(InvalidTraceQuery):
            normalize_trace_id(bad)


def test_a_query_defaults_to_the_last_hour_and_20_traces():
    query = TraceQuery().validated()

    assert (query.lookback, query.limit, query.errors) == ("1h", 20, False)
    assert TraceQuery(lookback="7d", limit=100, min_duration_ms=0).validated().limit == 100


@pytest.mark.parametrize(
    "query",
    [
        TraceQuery(lookback="2h"),
        TraceQuery(limit=0),
        TraceQuery(limit=101),
        TraceQuery(max_duration_ms=-0.5),
        TraceQuery(min_duration_ms=10, max_duration_ms=5),
    ],
)
def test_malformed_queries(query):
    with pytest.raises(InvalidTraceQuery):
        query.validated()


def test_trace_level_filters():
    assert TraceQuery().keeps(_summary())
    assert not TraceQuery(errors=True).keeps(_summary())
    assert TraceQuery(errors=True).keeps(_summary(errors=1))
    assert TraceQuery(min_duration_ms=100, max_duration_ms=100).keeps(_summary())
    assert not TraceQuery(min_duration_ms=100.5).keeps(_summary())
    assert not TraceQuery(max_duration_ms=99.9).keeps(_summary())


def test_services_are_counted_busiest_first():
    a, b, _ = fixtures.traces(NOW)

    assert service_counts(a.spans) == (
        ServiceCount("nexus-api", 1, 0),
        ServiceCount("zen-engine", 1, 0),
    )
    assert service_counts([*a.spans, *b.spans, b.spans[1]]) == (
        ServiceCount("ops-researcher", 3, 2),
        ServiceCount("nexus-api", 1, 0),
        ServiceCount("zen-engine", 1, 0),
    )


def test_the_root_is_the_earliest_span_without_a_parent():
    a, b, _ = fixtures.traces(NOW)

    assert summarize(a).root == TraceRoot("nexus-api", "GET /api/search")
    assert (summarize(b).spans, summarize(b).errors) == (2, 1)
    orphans = replace(b, spans=tuple(replace(s, parent_id="f" * 16) for s in reversed(b.spans)))
    assert summarize(orphans).root == TraceRoot("ops-researcher", "digest")
    empty = replace(b, spans=(), services=())
    assert summarize(empty).root == TraceRoot("", "")


def test_a_late_root_wins_over_earlier_children():
    early_child = Span("2" * 16, "9" * 16, "child", "x", "client", 0.0, 1.0, "ok")
    late_root = Span("1" * 16, None, "root", "y", "server", 5.0, 1.0, "ok")
    a = fixtures.traces(NOW)[0]

    assert summarize(replace(a, spans=(early_child, late_root))).root == TraceRoot("y", "root")
