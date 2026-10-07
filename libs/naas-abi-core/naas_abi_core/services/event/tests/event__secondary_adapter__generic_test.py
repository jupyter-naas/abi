"""Reusable contract for any ``IEventAdapter``, in-process or remote.

Concrete adapter tests subclass ``EventSecondaryAdapterContract`` and provide
an ``adapter`` fixture; the NATS client's subclass runs the same cases through
a real primary and broker.
"""

from __future__ import annotations

import datetime
import json
from abc import ABC, abstractmethod
from itertools import islice

import pytest

from naas_abi_core.services.event.EventFilter import FilterError
from naas_abi_core.services.event.EventPort import IEventAdapter

A, B = "urn:Type:A", "urn:Type:B"


def _ts(offset_seconds: int = 0) -> str:
    return (
        datetime.datetime(2026, 1, 1)  # noqa: DTZ001
        + datetime.timedelta(seconds=offset_seconds)
    ).isoformat()


class EventSecondaryAdapterContract(ABC):
    @pytest.fixture
    @abstractmethod
    def adapter(self) -> IEventAdapter:
        raise NotImplementedError()

    def _append(self, adapter: IEventAdapter, count: int, pad: int = 0) -> None:
        for i in range(count):
            adapter.append(
                f"urn:e{i}",
                A if i % 3 else B,
                _ts(i),
                json.dumps(
                    {"i": i, "status": "ok" if i % 2 else "fail", "pad": "p" * pad}
                ).encode(),
            )

    def test_query_stream_reads_what_query_reads(self, adapter: IEventAdapter):
        # About 600 KiB: more than one 500-event page and one 256 KiB frame.
        self._append(adapter, 1_200, pad=500)

        with adapter.query_stream() as events:
            streamed = list(events)

        assert streamed == adapter.query()
        assert [event.seq for event in streamed] == list(range(1, 1_201))

    @pytest.mark.parametrize(
        "filters",
        [
            {"event_type": A, "newest_first": True, "limit": 700},
            {"newest_first": True},
            {"since_seq": 100, "until_seq": 1_050, "limit": 600},
            {"event_type": B, "json_filter": {"status": ["ok"]}},
            {"search": '"i": 11', "newest_first": True},
            {"since_timestamp": _ts(10), "until_timestamp": _ts(900)},
            {"limit": 0},
        ],
    )
    def test_query_stream_applies_the_same_filters_as_query(
        self, adapter: IEventAdapter, filters: dict
    ):
        self._append(adapter, 1_100)

        with adapter.query_stream(**filters) as events:
            streamed = list(events)

        assert streamed == adapter.query(**filters)

    def test_query_stream_excludes_events_appended_after_it_opened(
        self, adapter: IEventAdapter
    ):
        self._append(adapter, 3)

        for newest_first in (False, True):
            stored = len(adapter.query())
            with adapter.query_stream(newest_first=newest_first) as events:
                adapter.append(f"urn:late{newest_first}", A, _ts(99), b"{}")
                assert len(list(events)) == stored

    def test_query_stream_can_stop_early(self, adapter: IEventAdapter):
        self._append(adapter, 1_200)

        with adapter.query_stream() as events:
            first = list(islice(events, 10))

        assert [event.seq for event in first] == list(range(1, 11))
        assert adapter.max_seq() == 1_200  # still usable

    def test_a_malformed_filter_raises_filter_error(self, adapter: IEventAdapter):
        self._append(adapter, 2)
        malformed = {"bad key!": ["x"]}

        with pytest.raises(FilterError):
            adapter.query(json_filter=malformed)
        with (
            pytest.raises(FilterError),
            adapter.query_stream(json_filter=malformed) as events,
        ):
            list(events)


class EventStorageContract(EventSecondaryAdapterContract):
    """What every event store (not a remote client) must do, on top of the
    shared contract: sequencing, filters, search, cursors and type summaries."""

    # ---------------------------------------------------------------------------
    # append
    # ---------------------------------------------------------------------------

    def test_append_assigns_monotonic_seq(self, adapter):
        a = adapter.append("urn:e1", "urn:Type:A", _ts(0), b"payload-1")
        b = adapter.append("urn:e2", "urn:Type:A", _ts(1), b"payload-2")
        c = adapter.append("urn:e3", "urn:Type:B", _ts(2), b"payload-3")

        assert a.seq == 1
        assert b.seq == 2
        assert c.seq == 3
        assert a.id == "urn:e1"
        assert a.event_type == "urn:Type:A"
        assert a.payload == b"payload-1"

    def test_append_rejects_duplicate_id(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p")
        with pytest.raises(Exception):
            adapter.append("urn:e1", "urn:Type:A", _ts(1), b"p2")

    # ---------------------------------------------------------------------------
    # query
    # ---------------------------------------------------------------------------

    def test_query_filters_by_event_type(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
        adapter.append("urn:e2", "urn:Type:B", _ts(1), b"p2")
        adapter.append("urn:e3", "urn:Type:A", _ts(2), b"p3")

        rows = adapter.query(event_type="urn:Type:A")
        assert [r.id for r in rows] == ["urn:e1", "urn:e3"]

    def test_query_orders_by_seq(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(10), b"p1")
        adapter.append(
            "urn:e2", "urn:Type:A", _ts(0), b"p2"
        )  # earlier timestamp, later seq

        rows = adapter.query(event_type="urn:Type:A")
        assert [r.seq for r in rows] == [1, 2]

    def test_query_time_window(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
        adapter.append("urn:e2", "urn:Type:A", _ts(10), b"p2")
        adapter.append("urn:e3", "urn:Type:A", _ts(20), b"p3")

        rows = adapter.query(since_timestamp=_ts(5), until_timestamp=_ts(15))
        assert [r.id for r in rows] == ["urn:e2"]

    def test_query_limit(self, adapter):
        for i in range(5):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        rows = adapter.query(limit=2)
        assert len(rows) == 2
        assert [r.seq for r in rows] == [1, 2]

    def test_query_since_seq(self, adapter):
        for i in range(3):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        rows = adapter.query(since_seq=1)
        assert [r.seq for r in rows] == [2, 3]

    def test_query_until_seq(self, adapter):
        for i in range(4):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        rows = adapter.query(until_seq=2)
        assert [r.seq for r in rows] == [1, 2]

    def test_query_since_and_until_seq(self, adapter):
        for i in range(5):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        rows = adapter.query(since_seq=1, until_seq=3)
        assert [r.seq for r in rows] == [2, 3]

    def test_max_seq(self, adapter):
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

    def test_query_newest_first_orders_seq_desc(self, adapter):
        for i in range(5):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        rows = adapter.query(newest_first=True)
        assert [r.seq for r in rows] == [5, 4, 3, 2, 1]

    def test_query_newest_first_with_limit_returns_most_recent(self, adapter):
        for i in range(5):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        rows = adapter.query(newest_first=True, limit=2)
        # The two MOST RECENT, not the two oldest.
        assert [r.seq for r in rows] == [5, 4]

    def test_query_newest_first_with_type_returns_last_n_of_that_type(self, adapter):
        # Interleave types; the rare type B is sparse and old relative to seq.
        adapter.append("urn:b1", "urn:Type:B", _ts(0), b"p")
        for i in range(10):
            adapter.append(f"urn:a{i}", "urn:Type:A", _ts(i + 1), b"p")
        adapter.append("urn:b2", "urn:Type:B", _ts(20), b"p")

        rows = adapter.query(event_type="urn:Type:B", newest_first=True, limit=100)
        # Both B events are returned even though A dominates the recent seq window.
        assert [r.id for r in rows] == ["urn:b2", "urn:b1"]

    def test_query_default_ordering_is_unchanged(self, adapter):
        for i in range(3):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")
        # Default (no newest_first) still oldest-first — cursor readers depend on it.
        rows = adapter.query()
        assert [r.seq for r in rows] == [1, 2, 3]

    # ---------------------------------------------------------------------------
    # search (substring over payload)
    # ---------------------------------------------------------------------------

    def test_query_search_matches_payload_substring(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"message":"disk full"}')
        adapter.append("urn:e2", "urn:Type:A", _ts(1), b'{"message":"all good"}')
        adapter.append("urn:e3", "urn:Type:A", _ts(2), b'{"message":"DISK pressure"}')

        rows = adapter.query(search="disk")
        # Case-insensitive over the raw JSON text.
        assert {r.id for r in rows} == {"urn:e1", "urn:e3"}

    def test_query_search_combines_with_type_and_newest_first(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"status":500}')
        adapter.append("urn:e2", "urn:Type:B", _ts(1), b'{"status":500}')
        adapter.append("urn:e3", "urn:Type:A", _ts(2), b'{"status":500}')

        rows = adapter.query(event_type="urn:Type:A", search="500", newest_first=True)
        assert [r.id for r in rows] == ["urn:e3", "urn:e1"]

    def test_query_search_escapes_like_wildcards(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"path":"a/b"}')
        adapter.append("urn:e2", "urn:Type:A", _ts(1), b'{"path":"axb"}')

        # "a%b" must match literally, not as the LIKE wildcard "a<anything>b".
        rows = adapter.query(search="a%b")
        assert rows == []

    # ---------------------------------------------------------------------------
    # cursor / query_for_consumer
    # ---------------------------------------------------------------------------

    def test_get_cursor_defaults_to_zero(self, adapter):
        assert adapter.get_cursor("c1", "urn:Type:A") == 0

    def test_set_cursor_seeks_and_can_move_backward(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
        adapter.append("urn:e2", "urn:Type:A", _ts(1), b"p2")
        adapter.query_for_consumer("c1", "urn:Type:A")
        assert adapter.get_cursor("c1", "urn:Type:A") == 2

        adapter.set_cursor("c1", "urn:Type:A", adapter.max_seq("urn:Type:A"))
        assert adapter.get_cursor("c1", "urn:Type:A") == 2
        assert adapter.query_for_consumer("c1", "urn:Type:A") == []

        # Repair a stale cursor after seq restart (cursor ahead of max).
        adapter.set_cursor("c1", "urn:Type:A", 0)
        assert adapter.get_cursor("c1", "urn:Type:A") == 0
        rows = adapter.query_for_consumer("c1", "urn:Type:A", limit=1)
        assert [r.id for r in rows] == ["urn:e1"]

    def test_query_for_consumer_advances_cursor(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")
        adapter.append("urn:e2", "urn:Type:A", _ts(1), b"p2")

        first = adapter.query_for_consumer("c1", "urn:Type:A")
        assert [r.id for r in first] == ["urn:e1", "urn:e2"]
        assert adapter.get_cursor("c1", "urn:Type:A") == 2

        second = adapter.query_for_consumer("c1", "urn:Type:A")
        assert second == []

    def test_query_for_consumer_isolated_per_consumer(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"p1")

        adapter.query_for_consumer("c1", "urn:Type:A")
        rows = adapter.query_for_consumer("c2", "urn:Type:A")
        assert [r.id for r in rows] == ["urn:e1"]

    def test_query_for_consumer_isolated_per_event_type(self, adapter):
        adapter.append("urn:e1", "urn:Type:A", _ts(0), b"pA")
        adapter.append("urn:e2", "urn:Type:B", _ts(1), b"pB")

        a_rows = adapter.query_for_consumer("c1", "urn:Type:A")
        assert [r.id for r in a_rows] == ["urn:e1"]
        b_rows = adapter.query_for_consumer("c1", "urn:Type:B")
        assert [r.id for r in b_rows] == ["urn:e2"]

    def test_query_for_consumer_respects_limit_and_advances_partially(self, adapter):
        for i in range(5):
            adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"p")

        first = adapter.query_for_consumer("c1", "urn:Type:A", limit=2)
        assert [r.seq for r in first] == [1, 2]
        assert adapter.get_cursor("c1", "urn:Type:A") == 2

        second = adapter.query_for_consumer("c1", "urn:Type:A", limit=2)
        assert [r.seq for r in second] == [3, 4]
        assert adapter.get_cursor("c1", "urn:Type:A") == 4

    # ---------------------------------------------------------------------------
    # list_event_types
    # ---------------------------------------------------------------------------

    def test_list_event_types_counts_each_type_with_its_latest_event(self, adapter):
        adapter.append("urn:e1", "urn:Type:B", _ts(0), b"1")
        adapter.append("urn:e2", "urn:Type:A", _ts(1), b"2")
        adapter.append("urn:e3", "urn:Type:B", _ts(2), b"3")

        summaries = adapter.list_event_types()

        assert [(s.event_type, s.count, s.last_seq) for s in summaries] == [
            ("urn:Type:A", 1, 2),
            ("urn:Type:B", 2, 3),
        ]
        assert summaries[1].last_timestamp == _ts(2)

    def test_list_event_types_of_an_empty_log(self, adapter):
        assert adapter.list_event_types() == []

    # ------------------------------------------------------------------
    # json_filter pushdown
    # ------------------------------------------------------------------

    def _people(self, adapter):
        for i, (name, status, team) in enumerate(
            [
                ("user-ana", "ok", "core"),
                ("user-bob", "fail", "web"),
                ("svc-cron", "ok", "core"),
                ("user-cy", "ok", "web"),
            ]
        ):
            adapter.append(
                f"urn:p{i}",
                "urn:Type:A",
                _ts(i),
                json.dumps(
                    {"i": i, "name": name, "status": status, "team": {"id": team}}
                ).encode(),
            )

    def _ids(self, adapter, json_filter):
        return [r.id for r in adapter.query(json_filter=json_filter)]

    def test_filter_on_an_equal_string(self, adapter):
        self._people(adapter)
        assert self._ids(adapter, {"status": "fail"}) == ["urn:p1"]

    def test_filter_on_a_list_of_values(self, adapter):
        self._people(adapter)
        assert self._ids(adapter, {"name": ["user-bob", "svc-cron"]}) == [
            "urn:p1",
            "urn:p2",
        ]

    def test_filter_on_a_number_range(self, adapter):
        self._people(adapter)
        assert self._ids(adapter, {"i": {"gte": 1, "lt": 3}}) == ["urn:p1", "urn:p2"]

    def test_filter_on_a_prefix(self, adapter):
        self._people(adapter)
        assert self._ids(adapter, {"name": {"prefix": "user-"}}) == [
            "urn:p0",
            "urn:p1",
            "urn:p3",
        ]

    def test_filter_on_a_nested_path(self, adapter):
        self._people(adapter)
        assert self._ids(adapter, {"team.id": "web", "status": "ok"}) == ["urn:p3"]

    def test_filter_on_presence(self, adapter):
        self._people(adapter)
        assert len(self._ids(adapter, {"missing": {"exists": False}})) == 4
        assert self._ids(adapter, {"missing": {"exists": True}}) == []

    def test_a_filtered_consumer_reads_and_advances_over_matches_only(self, adapter):
        self._people(adapter)

        rows = adapter.query_for_consumer(
            "c1", "urn:Type:A", json_filter={"status": "ok"}, limit=2
        )

        assert [r.id for r in rows] == ["urn:p0", "urn:p2"]
        assert adapter.get_cursor("c1", "urn:Type:A") == rows[-1].seq
