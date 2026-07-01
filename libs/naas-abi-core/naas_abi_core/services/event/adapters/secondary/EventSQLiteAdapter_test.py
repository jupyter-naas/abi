"""Tests for EventSQLiteAdapter."""

from __future__ import annotations

import datetime

import pytest

from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import (
    EventSQLiteAdapter,
)


@pytest.fixture()
def adapter(tmp_path):
    db = tmp_path / "events.sqlite"
    a = EventSQLiteAdapter(str(db))
    yield a
    a.close()


def _ts(offset_seconds: int = 0) -> str:
    return (
        datetime.datetime(2026, 1, 1, 0, 0, 0)
        + datetime.timedelta(seconds=offset_seconds)
    ).isoformat()


# ---------------------------------------------------------------------------
# append
# ---------------------------------------------------------------------------


def test_append_assigns_monotonic_seq(adapter):
    a = adapter.append("urn:e1", "urn:Type:A", _ts(0), b"payload-1")
    b = adapter.append("urn:e2", "urn:Type:A", _ts(1), b"payload-2")
    c = adapter.append("urn:e3", "urn:Type:B", _ts(2), b"payload-3")

    assert a.seq == 1
    assert b.seq == 2
    assert c.seq == 3
    assert a.id == "urn:e1"
    assert a.event_type == "urn:Type:A"
    assert a.payload == b"payload-1"


def test_append_rejects_duplicate_id(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p")
    with pytest.raises(Exception):
        adapter.append("urn:e1", "urn:Type:A", _ts(1), b"p2")


# ---------------------------------------------------------------------------
# query
# ---------------------------------------------------------------------------


def test_query_filters_by_event_type(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
    adapter.append("urn:e2", "urn:Type:B", _ts(1), b"p2")
    adapter.append("urn:e3", "urn:Type:A", _ts(2), b"p3")

    rows = adapter.query(event_type="urn:Type:A")
    assert [r.id for r in rows] == ["urn:e1", "urn:e3"]


def test_query_orders_by_seq(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(10), b"p1")
    adapter.append("urn:e2", "urn:Type:A", _ts(0), b"p2")  # earlier timestamp, later seq

    rows = adapter.query(event_type="urn:Type:A")
    assert [r.seq for r in rows] == [1, 2]


def test_query_time_window(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
    adapter.append("urn:e2", "urn:Type:A", _ts(10), b"p2")
    adapter.append("urn:e3", "urn:Type:A", _ts(20), b"p3")

    rows = adapter.query(since_timestamp=_ts(5), until_timestamp=_ts(15))
    assert [r.id for r in rows] == ["urn:e2"]


def test_query_limit(adapter):
    for i in range(5):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    rows = adapter.query(limit=2)
    assert len(rows) == 2
    assert [r.seq for r in rows] == [1, 2]


def test_query_since_seq(adapter):
    for i in range(3):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    rows = adapter.query(since_seq=1)
    assert [r.seq for r in rows] == [2, 3]


def test_query_until_seq(adapter):
    for i in range(4):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    rows = adapter.query(until_seq=2)
    assert [r.seq for r in rows] == [1, 2]


def test_query_since_and_until_seq(adapter):
    for i in range(5):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    rows = adapter.query(since_seq=1, until_seq=3)
    assert [r.seq for r in rows] == [2, 3]


def test_max_seq(adapter):
    assert adapter.max_seq() == 0
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p")
    adapter.append("urn:e2", "urn:Type:B", _ts(1), b"p")
    adapter.append("urn:e3", "urn:Type:A", _ts(2), b"p")
    assert adapter.max_seq() == 3
    assert adapter.max_seq(event_type="urn:Type:A") == 3
    assert adapter.max_seq(event_type="urn:Type:B") == 2
    assert adapter.max_seq(event_type="urn:Type:DoesNotExist") == 0


# ---------------------------------------------------------------------------
# newest_first ordering ("last N of a type")
# ---------------------------------------------------------------------------


def test_query_newest_first_orders_seq_desc(adapter):
    for i in range(5):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    rows = adapter.query(newest_first=True)
    assert [r.seq for r in rows] == [5, 4, 3, 2, 1]


def test_query_newest_first_with_limit_returns_most_recent(adapter):
    for i in range(5):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    rows = adapter.query(newest_first=True, limit=2)
    # The two MOST RECENT, not the two oldest.
    assert [r.seq for r in rows] == [5, 4]


def test_query_newest_first_with_type_returns_last_n_of_that_type(adapter):
    # Interleave types; the rare type B is sparse and old relative to seq.
    adapter.append("urn:b1", "urn:Type:B", _ts(0), b"p")
    for i in range(10):
        adapter.append(f"urn:a{i}", "urn:Type:A", _ts(i + 1), b"p")
    adapter.append("urn:b2", "urn:Type:B", _ts(20), b"p")

    rows = adapter.query(event_type="urn:Type:B", newest_first=True, limit=100)
    # Both B events are returned even though A dominates the recent seq window.
    assert [r.id for r in rows] == ["urn:b2", "urn:b1"]


def test_query_default_ordering_is_unchanged(adapter):
    for i in range(3):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
    # Default (no newest_first) still oldest-first — cursor readers depend on it.
    rows = adapter.query()
    assert [r.seq for r in rows] == [1, 2, 3]


# ---------------------------------------------------------------------------
# search (substring over payload)
# ---------------------------------------------------------------------------


def test_query_search_matches_payload_substring(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"message":"disk full"}')
    adapter.append("urn:e2", "urn:Type:A", _ts(1), b'{"message":"all good"}')
    adapter.append("urn:e3", "urn:Type:A", _ts(2), b'{"message":"DISK pressure"}')

    rows = adapter.query(search="disk")
    # Case-insensitive over the raw JSON text.
    assert {r.id for r in rows} == {"urn:e1", "urn:e3"}


def test_query_search_combines_with_type_and_newest_first(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"status":500}')
    adapter.append("urn:e2", "urn:Type:B", _ts(1), b'{"status":500}')
    adapter.append("urn:e3", "urn:Type:A", _ts(2), b'{"status":500}')

    rows = adapter.query(event_type="urn:Type:A", search="500", newest_first=True)
    assert [r.id for r in rows] == ["urn:e3", "urn:e1"]


def test_query_search_escapes_like_wildcards(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"path":"a/b"}')
    adapter.append("urn:e2", "urn:Type:A", _ts(1), b'{"path":"axb"}')

    # "a%b" must match literally, not as the LIKE wildcard "a<anything>b".
    rows = adapter.query(search="a%b")
    assert rows == []


# ---------------------------------------------------------------------------
# cursor / query_for_consumer
# ---------------------------------------------------------------------------


def test_get_cursor_defaults_to_zero(adapter):
    assert adapter.get_cursor("c1", "urn:Type:A") == 0


def test_query_for_consumer_advances_cursor(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
    adapter.append("urn:e2", "urn:Type:A", _ts(1), b"p2")

    first = adapter.query_for_consumer("c1", "urn:Type:A")
    assert [r.id for r in first] == ["urn:e1", "urn:e2"]
    assert adapter.get_cursor("c1", "urn:Type:A") == 2

    second = adapter.query_for_consumer("c1", "urn:Type:A")
    assert second == []


def test_query_for_consumer_isolated_per_consumer(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")

    adapter.query_for_consumer("c1", "urn:Type:A")
    rows = adapter.query_for_consumer("c2", "urn:Type:A")
    assert [r.id for r in rows] == ["urn:e1"]


def test_query_for_consumer_isolated_per_event_type(adapter):
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b"pA")
    adapter.append("urn:e2", "urn:Type:B", _ts(1), b"pB")

    a_rows = adapter.query_for_consumer("c1", "urn:Type:A")
    assert [r.id for r in a_rows] == ["urn:e1"]
    b_rows = adapter.query_for_consumer("c1", "urn:Type:B")
    assert [r.id for r in b_rows] == ["urn:e2"]


def test_query_for_consumer_respects_limit_and_advances_partially(adapter):
    for i in range(5):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")

    first = adapter.query_for_consumer("c1", "urn:Type:A", limit=2)
    assert [r.seq for r in first] == [1, 2]
    assert adapter.get_cursor("c1", "urn:Type:A") == 2

    second = adapter.query_for_consumer("c1", "urn:Type:A", limit=2)
    assert [r.seq for r in second] == [3, 4]
    assert adapter.get_cursor("c1", "urn:Type:A") == 4


# ---------------------------------------------------------------------------
# durability
# ---------------------------------------------------------------------------


def test_events_persist_across_reopens(tmp_path):
    db = str(tmp_path / "events.sqlite")
    a1 = EventSQLiteAdapter(db)
    a1.append("urn:e1", "urn:Type:A", _ts(0), b"payload")
    a1.close()

    a2 = EventSQLiteAdapter(db)
    try:
        rows = a2.query()
        assert [r.id for r in rows] == ["urn:e1"]
        assert rows[0].payload == b"payload"
    finally:
        a2.close()
