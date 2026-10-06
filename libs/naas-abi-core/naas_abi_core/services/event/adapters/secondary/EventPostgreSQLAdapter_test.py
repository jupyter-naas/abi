"""The PostgreSQL event log; set EVENT_TEST_POSTGRES_DSN to run it."""

from __future__ import annotations

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter import (
    EventPostgreSQLAdapter,
)
from naas_abi_core.services.event.tests.event__secondary_adapter__generic_test import (
    EventStorageContract,
    _ts,
)


@pytest.fixture
def connection():
    dsn = os.environ.get("EVENT_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("Set EVENT_TEST_POSTGRES_DSN to run the PostgreSQL event log")
    schema = "event_test_" + uuid4().hex
    yield {"dsn": dsn, "schema": schema}
    import psycopg

    with psycopg.connect(dsn, autocommit=True) as conn:
        conn.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')


class TestEventPostgreSQLAdapter(EventStorageContract):
    @pytest.fixture
    def adapter(self, connection):
        adapter = EventPostgreSQLAdapter(**connection)
        yield adapter
        adapter.close()


def test_events_persist_across_reopens(connection):
    first = EventPostgreSQLAdapter(**connection)
    first.append("urn:e1", "urn:Type:A", _ts(0), b"payload")
    first.close()

    second = EventPostgreSQLAdapter(**connection)
    try:
        assert [(r.id, r.payload) for r in second.query()] == [("urn:e1", b"payload")]
        assert second.append("urn:e2", "urn:Type:A", _ts(1), b"p").seq == 2
    finally:
        second.close()


def test_two_engines_appending_while_a_consumer_reads_lose_nothing(connection):
    # Every event must reach a consumer that reads while others commit: a
    # sequence committed out of order would let its cursor pass a late event.
    engines = [EventPostgreSQLAdapter(**connection) for _ in range(2)]
    reader = EventPostgreSQLAdapter(**connection)
    seen: list[str] = []
    done = threading.Event()

    def consume() -> None:
        while True:
            finished = done.is_set()
            seen.extend(r.id for r in reader.query_for_consumer("c", "urn:Type:A"))
            if finished:
                return

    def append(i: int) -> None:
        engines[i % 2].append(f"urn:e{i}", "urn:Type:A", _ts(i), b"{}")

    consumer = threading.Thread(target=consume, daemon=True)
    consumer.start()
    try:
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(append, range(200)))
    finally:
        done.set()  # the consumer stops even if an append failed
        consumer.join(timeout=30)

    assert not consumer.is_alive()
    assert sorted(seen) == sorted(f"urn:e{i}" for i in range(200))
    assert len(seen) == 200
    assert [r.seq for r in reader.query()] == list(range(1, 201))
    for adapter in (*engines, reader):
        adapter.close()


def test_payloads_are_kept_byte_for_byte(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    raw = [
        b'{"b": 1,   "a": [1, 2]}',
        b"not json",
        b"\xff\x00binary",
        b'{"x": "\\u0000"}',
    ]
    for i, payload in enumerate(raw):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), payload)

    assert [r.payload for r in adapter.query()] == raw
    # Filters skip what is not JSON; search still reads every payload.
    assert [r.id for r in adapter.query(json_filter={"b": "1"})] == ["urn:e0"]
    assert [r.id for r in adapter.query(search="NOT JSON")] == ["urn:e1"]
    adapter.close()


def test_a_numeric_filter_ignores_values_that_are_not_numbers(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    for i, value in enumerate([5, "7", "seven", None, 9.5]):
        adapter.append(
            f"urn:e{i}", "urn:Type:A", _ts(i), json.dumps({"n": value}).encode()
        )

    assert [r.id for r in adapter.query(json_filter={"n": {"gt": 6}})] == [
        "urn:e1",
        "urn:e4",
    ]
    adapter.close()


def test_like_wildcards_in_filters_match_literally(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    adapter.append("urn:e1", "urn:Type:A", _ts(0), b'{"path": "a_b"}')
    adapter.append("urn:e2", "urn:Type:A", _ts(1), b'{"path": "axb"}')

    assert [r.id for r in adapter.query(json_filter={"path": {"prefix": "a_"}})] == [
        "urn:e1"
    ]
    adapter.close()


def test_an_invalid_schema_name_is_refused():
    with pytest.raises(ValueError):
        EventPostgreSQLAdapter(dsn="postgresql://x", schema='bad"; DROP')


def test_the_factory_builds_a_service_on_the_postgresql_log(connection):
    from naas_abi_core.services.event.EventFactory import EventFactory

    service = EventFactory.EventServicePostgreSQL(**connection)

    assert isinstance(service.adapter, EventPostgreSQLAdapter)
    assert service.event_types() == []
    service.adapter.close()


# --- what the archive job relies on ------------------------------------------------------


def _iso(days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


def test_removing_archived_events_never_reuses_their_numbers(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    for i in range(3):
        adapter.append(f"urn:e{i}", "urn:Type:A", _ts(i), b"{}")

    assert adapter.remove_through(2) == 2
    assert [r.seq for r in adapter.query()] == [3]
    assert adapter.remove_through(3) == 1
    assert adapter.append("urn:e3", "urn:Type:A", _ts(3), b"{}").seq == 4
    adapter.close()

    reopened = EventPostgreSQLAdapter(**connection)
    assert reopened.append("urn:e4", "urn:Type:A", _ts(4), b"{}").seq == 5
    reopened.close()


def test_archiving_stops_before_the_first_recent_event(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    for i, days_ago in enumerate([10, 9, 1, 8]):  # the last one is backdated
        adapter.append(f"urn:e{i}", "urn:Type:A", _iso(days_ago), b"{}")

    boundary = adapter.archivable_through(
        _iso(7), consumers_active_since=datetime.now(UTC) - timedelta(days=7)
    )

    assert boundary.through == 2
    assert boundary.idle_consumers == []
    adapter.close()


def test_an_active_consumer_holds_archiving_back_to_its_cursor(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    for i in range(3):
        adapter.append(f"urn:e{i}", "urn:Type:A", _iso(10), b"{}")
    adapter.query_for_consumer("reader", "urn:Type:A", limit=1)

    boundary = adapter.archivable_through(
        _iso(7), consumers_active_since=datetime.now(UTC) - timedelta(days=7)
    )

    assert boundary.through == 1
    adapter.close()


def test_an_idle_consumer_does_not_hold_archiving_back(connection):
    adapter = EventPostgreSQLAdapter(**connection)
    for i in range(3):
        adapter.append(f"urn:e{i}", "urn:Type:A", _iso(10), b"{}")
    adapter.query_for_consumer("gone", "urn:Type:A", limit=1)

    boundary = adapter.archivable_through(
        _iso(7), consumers_active_since=datetime.now(UTC) + timedelta(days=1)
    )

    assert boundary.through == 3
    assert boundary.idle_consumers == [("gone", "urn:Type:A")]
    adapter.close()
