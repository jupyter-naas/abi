"""Archiving old events from PostgreSQL into the Dataset Service.

Runs against a real PostgreSQL (EVENT_TEST_POSTGRES_DSN) and a local DuckLake.
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from naas_abi_core.module.jobs import JobContext
from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory
from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter import (
    EventPostgreSQLAdapter,
)
from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter_test import (
    connection,  # noqa: F401 - the PostgreSQL fixture
)
from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLArchive import (
    ARCHIVE_DATASET,
    EVENT_ARCHIVE_OWNER,
    EventArchiveJobs,
)

A = "urn:Type:A"


def iso(days_ago: float) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


@pytest.fixture
def events(connection):  # noqa: F811
    adapter = EventPostgreSQLAdapter(**connection)
    yield adapter
    adapter.close()


@pytest.fixture
def datasets(tmp_path):
    return DatasetFactory.DatasetServiceDuckLake(
        catalog=f"sqlite:{tmp_path / 'catalog.sqlite'}",
        data_path=str(tmp_path / "data") + "/",
    )


def jobs(events, datasets, **options) -> EventArchiveJobs:
    return EventArchiveJobs(events, datasets, namespace="events_test", **options)


def archived(datasets) -> list[dict]:
    return datasets.query(
        f"SELECT seq, id, event_type, timestamp, payload, payload_encoding "
        f"FROM {ARCHIVE_DATASET} ORDER BY seq",
        namespace="events_test",
    ).rows


def test_events_older_than_seven_days_move_to_the_dataset(events, datasets):
    oldest = iso(10)
    events.append("urn:e0", A, oldest, b'{"n": 0}')
    events.append("urn:e1", A, iso(8), b'{"n": 1}')
    events.append("urn:e2", A, iso(1), b'{"n": 2}')

    report = jobs(events, datasets).run()

    assert report.archived == 2
    assert [r.id for r in events.query()] == ["urn:e2"]
    rows = archived(datasets)
    assert [(r["seq"], r["id"], r["payload"]) for r in rows] == [
        (1, "urn:e0", '{"n": 0}'),
        (2, "urn:e1", '{"n": 1}'),
    ]
    assert {r["payload_encoding"] for r in rows} == {"utf-8"}
    assert rows[0]["timestamp"] == oldest  # kept exactly as given


def test_payloads_that_are_not_utf8_keep_their_bytes(events, datasets):
    events.append("urn:e0", A, iso(10), b"\xff\x00raw")

    jobs(events, datasets).run()

    (row,) = archived(datasets)
    assert row["payload_encoding"] == "base64"
    assert base64.b64decode(row["payload"]) == b"\xff\x00raw"


def test_large_backlogs_are_archived_in_batches(events, datasets):
    for i in range(5):
        events.append(f"urn:e{i}", A, iso(10), b"{}")

    report = jobs(events, datasets, batch_rows=2).run()

    assert (report.archived, report.batches) == (5, 3)
    assert [r["seq"] for r in archived(datasets)] == [1, 2, 3, 4, 5]
    assert events.query() == []


def test_an_interrupted_run_is_finished_without_duplicates(
    events, datasets, monkeypatch
):
    for i in range(4):
        events.append(f"urn:e{i}", A, iso(10), b"{}")
    archive = jobs(events, datasets, batch_rows=2)
    real_remove = events.remove_through
    calls = []

    def crash_after_the_first_write(seq: int) -> int:
        calls.append(seq)
        if len(calls) == 2:  # the first batch's removal, after its write
            raise ConnectionError("engine killed")
        return real_remove(seq)

    monkeypatch.setattr(events, "remove_through", crash_after_the_first_write)
    with pytest.raises(ConnectionError):
        archive.run()
    monkeypatch.setattr(events, "remove_through", real_remove)

    archive.run()

    assert [r["seq"] for r in archived(datasets)] == [1, 2, 3, 4]
    assert events.query() == []


def test_an_active_consumer_holds_archiving_back(events, datasets):
    for i in range(3):
        events.append(f"urn:e{i}", A, iso(10), b"{}")
    events.query_for_consumer("reader", A, limit=1)

    report = jobs(events, datasets).run()

    assert report.archived == 1
    assert [r.seq for r in events.query_for_consumer("reader", A)] == [2, 3]


def test_an_idle_consumer_is_reported_and_does_not_hold_archiving_back(
    events, datasets
):
    for i in range(3):
        events.append(f"urn:e{i}", A, iso(1), b"{}")
    events.query_for_consumer("gone", A, limit=1)

    # Eight days later, the consumer has not read for more than the window.
    report = jobs(events, datasets).run(now=datetime.now(UTC) + timedelta(days=8))

    assert report.archived == 3
    assert report.idle_consumers == [("gone", A)]


def test_numbering_continues_once_everything_is_archived(events, datasets):
    events.append("urn:e0", A, iso(10), b"{}")
    jobs(events, datasets).run()

    assert events.append("urn:e1", A, iso(0), b"{}").seq == 2


def test_nothing_to_archive_is_a_quiet_run(events, datasets):
    events.append("urn:e0", A, iso(1), b"{}")

    report = jobs(events, datasets).run()

    assert (report.archived, report.batches) == (0, 0)


def test_a_cancelled_run_stops_between_batches(events, datasets):
    for i in range(6):
        events.append(f"urn:e{i}", A, iso(10), b"{}")
    ctx = JobContext("run-1", "event_archive", 1, {}, {})
    archive = jobs(events, datasets, batch_rows=2)
    write = datasets.write_stream

    def cancel_after_a_batch(*args, **kwargs):
        result = write(*args, **kwargs)
        ctx.cancelled.set()
        return result

    datasets.write_stream = cancel_after_a_batch  # type: ignore[method-assign]
    report = archive.run(ctx=ctx)

    assert report.archived == 2
    assert [r["seq"] for r in archived(datasets)] == [1, 2]
    assert [r.seq for r in events.query()] == [3, 4, 5, 6]


def test_the_job_runs_hourly():
    (descriptor,) = EventArchiveJobs.jobs

    assert descriptor.name == "event_archive"
    assert [t.kind for t in descriptor.triggers] == ["cron"]


def test_the_adapter_offers_its_archive_job_when_datasets_are_available(
    connection,  # noqa: F811
    datasets,
):
    services = SimpleNamespace(dataset=datasets, dataset_available=lambda: True)
    adapter = EventPostgreSQLAdapter(**connection)

    (owner,) = adapter.job_owners(services).items()
    assert owner[0] == EVENT_ARCHIVE_OWNER
    assert isinstance(owner[1], EventArchiveJobs)

    no_datasets = SimpleNamespace(dataset=None, dataset_available=lambda: False)
    assert adapter.job_owners(no_datasets) == {}
    adapter.close()

    kept = EventPostgreSQLAdapter(**connection, archive_after_days=None)
    assert kept.job_owners(services) == {}
    kept.close()
