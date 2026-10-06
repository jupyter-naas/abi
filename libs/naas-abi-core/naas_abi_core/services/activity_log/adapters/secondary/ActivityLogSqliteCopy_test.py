"""Copying the per-actor SQLite activity logs into the Document Service."""

from __future__ import annotations

import math
import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest
from naas_abi_core.module.jobs import JobContext
from naas_abi_core.services.activity_log.ActivityLogPort import ActivityEvent
from naas_abi_core.services.activity_log.adapters.secondary import (
    ActivityLogSqliteCopy as copy_module,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogDocumentAdapter import (
    NAMESPACE,
    ActivityLogDocumentAdapter,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogDocumentAdapter_test import (
    _postgres_root,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteCopy import (
    ACTIVITY_LOG_JOBS_OWNER,
    ActivityLogCopyJobs,
)
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
)
from naas_abi_core.services.document.DocumentService import DocumentService

START = datetime(2026, 3, 1, 9, 0, tzinfo=UTC)


@pytest.fixture(params=["sqlite", "postgresql"])
def root(request, tmp_path):
    """The engine's document root."""
    if request.param == "sqlite":
        adapter = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        root = DocumentService._for_engine(adapter)
    else:
        root, adapter = _postgres_root()
    yield root
    adapter.close()


@pytest.fixture
def engine_dir(tmp_path, monkeypatch):
    """The engine's working directory: config paths are relative to it."""
    workdir = tmp_path / "project"
    (workdir / "storage").mkdir(parents=True)
    monkeypatch.chdir(workdir)
    return workdir


@pytest.fixture
def target(root):
    adapter = ActivityLogDocumentAdapter()
    adapter.wire_services(SimpleNamespace(document=root))
    return adapter


def services(root, available=True):
    return SimpleNamespace(document=root, document_available=lambda: available)


@pytest.fixture
def jobs(target, root) -> ActivityLogCopyJobs:
    ((owner_id, owner),) = target.job_owners(services(root)).items()
    assert owner_id == ACTIVITY_LOG_JOBS_OWNER
    return owner


def sqlite_log(engine_dir, events, data_dir="storage/activity_log"):
    """Events recorded the old way: one SQLite file per actor."""
    source = ActivityLogSqliteAdapter(str(engine_dir / data_dir))
    for event in events:
        source.record(event)
    source.shutdown()
    return source


def event(actor, n, **attributes):
    return ActivityEvent(
        actor_id=actor,
        event_type=f"http.request.{n}",
        timestamp=START + timedelta(minutes=n),
        correlation_id=f"req-{n}",
        attributes={"n": n, **attributes},
    )


ALICE = "user:alice"
SERVICE = "service:triple/store"  # a slash: the file name is URL-encoded


@pytest.fixture
def old_log(engine_dir):
    events = [event(ALICE, n) for n in range(1, 4)] + [
        event(SERVICE, n) for n in range(1, 3)
    ]
    sqlite_log(engine_dir, events)
    return events


def ctx(payload=None):
    return JobContext(
        "run-1", "activity_log_migrate", 1, {"kind": "manual"}, payload or {}
    )


def content(events):
    return [(e.event_type, e.timestamp, e.correlation_id, e.attributes) for e in events]


def by_actor(report):
    return {row["actor_id"]: row for row in report["by_actor"]}


# --- the offer ---------------------------------------------------------------------------


def test_the_document_adapter_offers_the_copy_when_documents_are_available(
    target, root
):
    ((owner_id, owner),) = target.job_owners(services(root)).items()

    assert owner_id == "naas_abi_core.activity_log"
    (descriptor,) = owner.jobs
    assert descriptor.name == "activity_log_migrate"
    assert descriptor.triggers == ()  # Run now only
    assert owner.missing_job_handlers() == set()
    assert target.job_owners(services(root, available=False)) == {}


# --- dry run and copy --------------------------------------------------------------------


def test_a_dry_run_counts_each_actor_s_events_and_writes_nothing(jobs, target, old_log):
    report = jobs.migrate(ctx())

    assert report["mode"] == "dry-run"
    assert report["data_dir"] == "storage/activity_log"
    assert (report["actors"], report["events"], report["missing"]) == (2, 5, 5)
    assert (report["present"], report["copied"], report["rejected"]) == (0, 0, 0)
    assert by_actor(report)[ALICE] == {
        "actor_id": ALICE,
        "events": 3,
        "present": 0,
        "missing": 3,
        "copied": 0,
        "rejected": 0,
    }
    assert target.list_actors() == []


def test_applying_copies_every_actor_s_events_in_order(jobs, target, old_log):
    report = jobs.migrate(ctx({"apply": True}))

    assert report["mode"] == "applied"
    assert (report["copied"], report["missing"]) == (5, 5)
    assert sorted(target.list_actors()) == sorted([ALICE, SERVICE])
    copied = target.query(ALICE)
    assert content(copied) == content(old_log[:3])
    assert [e.seq for e in copied] == [1, 2, 3]
    assert content(target.query(SERVICE)) == content(old_log[3:])


def test_events_recorded_since_the_switch_keep_their_numbers(jobs, target, old_log):
    live = ActivityEvent(actor_id=ALICE, event_type="login")
    target.record(live)

    jobs.migrate(ctx({"apply": True}))

    events = target.query(ALICE)
    assert [e.event_type for e in events] == ["login"] + [
        e.event_type for e in old_log[:3]
    ]
    assert [e.seq for e in events] == [1, 2, 3, 4]


def test_running_again_copies_nothing(jobs, target, old_log):
    jobs.migrate(ctx({"apply": True}))

    dry = jobs.migrate(ctx())
    again = jobs.migrate(ctx({"apply": True}))

    for report in (dry, again):
        assert (report["events"], report["present"], report["missing"]) == (5, 5, 0)
        assert report["copied"] == 0
    assert len(target.query(ALICE)) == 3


def test_events_added_to_a_sqlite_log_later_are_copied_next_time(
    jobs, target, engine_dir, old_log
):
    jobs.migrate(ctx({"apply": True}))
    sqlite_log(engine_dir, [event(ALICE, 9)])

    report = jobs.migrate(ctx({"apply": True}))

    assert by_actor(report)[ALICE]["copied"] == 1
    assert [e.event_type for e in target.query(ALICE)][-1] == "http.request.9"


class Interrupted(Exception):
    pass


def stop_before_the_mark(jobs, monkeypatch, after_marks):
    """The run stops (a timeout, a restart) between writing events and saving
    the mark that records them, after ``after_marks`` marks were saved."""
    put = jobs.marks.put
    saved = []

    def put_or_stop(*args, **kwargs):
        if len(saved) == after_marks:
            raise Interrupted()
        saved.append(args)
        return put(*args, **kwargs)

    monkeypatch.setattr(jobs.marks, "put", put_or_stop)
    with pytest.raises(Interrupted):
        jobs.migrate(ctx({"apply": True}))
    monkeypatch.setattr(jobs.marks, "put", put)


def test_a_run_stopped_before_its_mark_copies_nothing_twice(
    jobs, target, engine_dir, monkeypatch
):
    monkeypatch.setattr(copy_module, "BATCH", 2)
    events = [event(ALICE, n) for n in range(1, 6)]
    sqlite_log(engine_dir, events)
    stop_before_the_mark(jobs, monkeypatch, after_marks=1)  # events 3 and 4 unmarked
    assert len(target.query(ALICE)) == 4

    dry = jobs.migrate(ctx())
    report = jobs.migrate(ctx({"apply": True}))

    assert (dry["present"], dry["missing"]) == (4, 1)
    assert (report["present"], report["copied"]) == (4, 1)
    assert content(target.query(ALICE)) == content(events)


def test_identical_events_are_each_copied_once(jobs, target, engine_dir, monkeypatch):
    monkeypatch.setattr(copy_module, "BATCH", 1)
    twins = [event(ALICE, 1), event(ALICE, 1), event(ALICE, 2)]
    sqlite_log(engine_dir, twins)
    stop_before_the_mark(jobs, monkeypatch, after_marks=0)  # the first twin, unmarked

    report = jobs.migrate(ctx({"apply": True}))

    assert (report["present"], report["copied"]) == (1, 2)
    assert content(target.query(ALICE)) == content(twins)


def test_events_the_documents_refuse_are_reported_and_skipped(jobs, target, engine_dir):
    events = [event(ALICE, 1), event(ALICE, 2, ratio=math.nan), event(ALICE, 3)]
    sqlite_log(engine_dir, events)

    dry = jobs.migrate(ctx())
    assert (dry["missing"], dry["rejected"], dry["copied"]) == (3, 1, 0)
    assert [r["source_seq"] for r in dry["rejected_events"]] == [2]

    report = jobs.migrate(ctx({"apply": True}))

    assert (report["copied"], report["rejected"]) == (2, 1)
    (rejected,) = report["rejected_events"]
    assert rejected["actor_id"] == ALICE and rejected["source_seq"] == 2
    assert "finite" in rejected["error"]
    assert [e.event_type for e in target.query(ALICE)] == [
        "http.request.1",
        "http.request.3",
    ]
    again = jobs.migrate(ctx({"apply": True}))
    assert (again["copied"], again["missing"], again["rejected"]) == (0, 0, 1)
    assert again["rejected_events"] == []


def test_each_source_directory_is_copied_on_its_own(jobs, target, engine_dir):
    sqlite_log(engine_dir, [event(ALICE, 1)], data_dir="storage/host-a")
    sqlite_log(engine_dir, [event(ALICE, 2)], data_dir="storage/host-b")

    jobs.migrate(ctx({"data_dir": "storage/host-a", "apply": True}))
    report = jobs.migrate(ctx({"data_dir": "storage/host-b", "apply": True}))

    assert report["copied"] == 1
    assert len(target.query(ALICE)) == 2


def test_marks_live_beside_the_activity_log(jobs, root, old_log):
    jobs.migrate(ctx({"apply": True}))

    assert "sqlite_copies" in root.for_namespace(NAMESPACE).collections()


# --- payload ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "data_dir",
    ["../outside", "storage/../../outside", "/etc", "storage/link-out"],
)
def test_data_dir_must_stay_inside_the_engine_storage(jobs, engine_dir, data_dir):
    outside = engine_dir.parent / "outside"
    outside.mkdir(exist_ok=True)
    sqlite_log(outside.parent, [event(ALICE, 1)], data_dir="outside")
    os.symlink(outside, engine_dir / "storage" / "link-out")

    with pytest.raises(ValueError, match="storage"):
        jobs.migrate(ctx({"data_dir": data_dir}))


@pytest.mark.parametrize(
    "payload, message",
    [
        ({"data_dir": "storage/missing"}, "not a directory"),
        ({"data_dir": 3}, "data_dir"),
        ({"data_dir": ""}, "data_dir"),
        ({"apply": "yes"}, "apply"),
        ({"dir": "storage"}, "dir"),
    ],
)
def test_invalid_payloads_are_refused(jobs, engine_dir, payload, message):
    with pytest.raises(ValueError, match=message):
        jobs.migrate(ctx(payload))
    assert not (engine_dir / "storage" / "missing").exists()


def test_long_actor_lists_are_cut_to_fit_the_run_record(jobs, old_log, monkeypatch):
    monkeypatch.setattr(copy_module, "MAX_LISTED", 1)

    report = jobs.migrate(ctx())

    assert len(report["by_actor"]) == 1
    assert report["by_actor_omitted"] == 1
    assert report["actors"] == 2


def test_a_cancelled_copy_stops_between_actors(jobs, target, old_log):
    context = ctx({"apply": True})
    context.cancelled.set()

    report = jobs.migrate(context)

    assert report["actors"] == 0
    assert target.list_actors() == []
    assert any("Cancelled" in line for line in context.logs)


def test_a_failing_document_service_stops_the_copy_without_skipping(
    jobs, target, engine_dir, monkeypatch
):
    sqlite_log(engine_dir, [event(ALICE, 1), event(ALICE, 2)])

    def broken(event):
        raise ValueError("Type changes are rejected")  # not about the event

    record = target.record
    monkeypatch.setattr(target, "record", broken)
    with pytest.raises(ValueError, match="Type changes"):
        jobs.migrate(ctx({"apply": True}))
    monkeypatch.setattr(target, "record", record)

    report = jobs.migrate(ctx({"apply": True}))
    assert (report["copied"], report["rejected"]) == (2, 0)
