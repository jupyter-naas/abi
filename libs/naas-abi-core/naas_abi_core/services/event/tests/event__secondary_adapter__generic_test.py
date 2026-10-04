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


def _ts(offset_seconds: int) -> str:
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
        with pytest.raises(FilterError):
            with adapter.query_stream(json_filter=malformed) as events:
                list(events)
