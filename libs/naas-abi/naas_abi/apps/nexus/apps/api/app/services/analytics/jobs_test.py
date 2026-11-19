"""The rollups' background work: the log's consumer, the one-time backfill, the purge.

A real EventService on SQLite holds the log; the rollups are SQLite tables, and
PostgreSQL ones too when a database is given (it is emptied):
ANALYTICS_TEST_POSTGRES_DSN=postgresql+asyncpg://user:pass@host:5432/db
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    AnalyticsEventModel,
    AnalyticsHourlyModel,
    AnalyticsPageModel,
    AnalyticsSessionModel,
    ConversationModel,
    MessageModel,
    MessageToolModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics import jobs as jobs_module
from naas_abi.apps.nexus.apps.api.app.services.analytics.jobs import AnalyticsJobs
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import (
    BACKFILL_JOB,
    CONSUMER_ID,
)
from naas_abi_core.services.event.adapters.secondary.EventSQLiteAdapter import EventSQLiteAdapter
from naas_abi_core.services.event.EventService import EventService
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

NOW = datetime.now(UTC).replace(microsecond=0)
POSTGRES_DSN = os.environ.get("ANALYTICS_TEST_POSTGRES_DSN")


def _iso(moment: datetime) -> str:
    return moment.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def payload(event_id: str, *, at: datetime = NOW, workspace: str = "ws-1") -> dict:
    return {
        "event_id": event_id,
        "timestamp": _iso(at),
        "session_id": "s-1",
        "event_name": "page_viewed",
        "user_id": "alice",
        "workspace_id": workspace,
        "page_path": "/workspace/ws-1/home",
    }


def publish(events: EventService, data: dict, *, organization: str | None = None) -> None:
    events.publish(
        AnalyticsEventRecorded(
            event_id=data["event_id"],
            timestamp=data["timestamp"],
            event_name=data["event_name"],
            user_id=data["user_id"],
            workspace_id=data["workspace_id"],
            organization_id=organization,
            session_id=data["session_id"],
            page_path=data["page_path"],
            payload_json=json.dumps(data),
        )
    )


class FakeLegacy:
    """The removed app's object-storage files: its raw events by file name (None for
    an unreadable one), which were deleted and which set aside."""

    def __init__(self, found: list[dict | None], *, readable: bool = True) -> None:
        self.files: dict[str, dict | None] = {f"f{i}.json": e for i, e in enumerate(found)}
        self.readable = readable
        self.deleted = 0
        self.gone: list[str] = []
        self.aside: list[str] = []

    @property
    def found(self) -> list[dict | None]:
        return list(self.files.values())

    def add(self, name: str, event: dict | None) -> None:
        self.files[name] = event

    def list_events(self) -> list[tuple[str, dict | None]]:
        if not self.readable:
            raise ConnectionError("object storage unreachable")
        return [(n, dict(e) if e is not None else None) for n, e in self.files.items()]

    def delete_replayed(self, names: list[str]) -> int:
        self.deleted += 1
        for name in names:
            self.files.pop(name, None)
        self.gone += names
        return len(names)

    def set_aside(self, names: list[str]) -> int:
        for name in names:
            self.files.pop(name, None)
        self.aside += names
        return len(names)


@pytest_asyncio.fixture(params=["sqlite", "postgresql"])
async def sessions(request, tmp_path):
    if request.param == "postgresql" and not POSTGRES_DSN:
        pytest.skip("ANALYTICS_TEST_POSTGRES_DSN is not set")
    url = (
        f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}"
        if request.param == "sqlite"
        else POSTGRES_DSN
    )
    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as db:
        db.add(UserModel(id="alice", email="alice@example.com", name="Alice"))
        db.add(WorkspaceModel(id="ws-1", name="W", slug="w", owner_id="alice"))
        await db.commit()
    yield factory
    await engine.dispose()


@pytest.fixture
def events(tmp_path) -> EventService:
    return EventService(EventSQLiteAdapter(str(tmp_path / "events.sqlite")))


async def _count(sessions, model) -> int:
    async with sessions() as db:
        return (await db.execute(select(func.count()).select_from(model))).scalar_one()


async def _hourly_total(sessions) -> int:
    async with sessions() as db:
        return (
            await db.execute(select(func.coalesce(func.sum(AnalyticsHourlyModel.count), 0)))
        ).scalar_one()


@pytest.mark.asyncio
async def test_the_consumer_applies_each_logged_event_once(sessions, events) -> None:
    jobs = AnalyticsJobs(sessions, events=events)
    for index in range(3):
        publish(events, payload(f"e-{index}"))
    assert await jobs.drain() == 3
    assert await jobs.drain() == 0
    publish(events, payload("e-3"))
    assert await jobs.drain() == 1
    assert await _hourly_total(sessions) == 4
    assert await _count(sessions, AnalyticsSessionModel) == 1


@pytest.mark.asyncio
async def test_a_batch_whose_write_fails_is_read_again(sessions, events, monkeypatch) -> None:
    jobs = AnalyticsJobs(sessions, events=events)
    publish(events, payload("e-1"))
    publish(events, payload("e-2"))

    original = jobs_module.AnalyticsRollups.apply

    async def broken(self, payloads):
        raise RuntimeError("database down")

    async def silent() -> bool:
        return False

    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply", broken)
    monkeypatch.setattr(jobs, "_database_answers", silent)
    with pytest.raises(jobs_module.Unavailable):
        await jobs.drain()
    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply", original)
    monkeypatch.undo()
    assert await jobs.drain() == 2
    assert await _hourly_total(sessions) == 2


@pytest.mark.asyncio
async def test_the_backfill_replays_45_days_of_the_log_and_every_legacy_event_once(
    sessions, events
) -> None:
    # Two consumers' worth: what was logged before the rollups existed.
    publish(events, payload("logged"))
    publish(events, payload("logged-too-old", at=NOW - timedelta(days=50)))
    legacy = [
        {**payload("legacy"), "user_email": "alice@example.com"},
        payload("legacy-old", at=NOW - timedelta(days=60)),
        payload("legacy-ancient", at=NOW - timedelta(days=800)),
        {**payload("logged")},  # also in the log: counted once
        {"not": "an event"},
    ]
    jobs = AnalyticsJobs(sessions, events=events, legacy=FakeLegacy(legacy))
    assert await jobs.backfill() == 4
    assert await jobs.backfill() is None  # recorded as done

    async with sessions() as db:
        rows = (await db.execute(select(AnalyticsEventModel))).scalars().all()
    # Raw rows within retention only; past it the legacy events are in the rollups.
    assert sorted(json.loads(r.payload)["event_id"] for r in rows) == ["legacy", "logged"]
    assert all("alice@example.com" not in r.payload for r in rows)
    assert await _hourly_total(sessions) == 4
    async with sessions() as db:
        hours = (await db.execute(select(AnalyticsHourlyModel.bucket_hour))).scalars().all()
    oldest = min(hours)
    assert oldest < (NOW - timedelta(days=799)).replace(tzinfo=None)
    # The consumer then reads the same log: nothing is counted twice (the log's own
    # event past retention is not counted: the log is replayed for 45 days).
    assert await jobs.drain() == 2
    assert await _hourly_total(sessions) == 4


@pytest.mark.asyncio
async def test_a_backfill_another_process_started_is_left_to_it(sessions, events) -> None:
    first = AnalyticsJobs(sessions, events=events, legacy=FakeLegacy([]))
    async with sessions() as db:
        from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
            AnalyticsSecondaryAdapterPostgresEvents,
        )

        port = AnalyticsSecondaryAdapterPostgresEvents(db)
        assert await port.claim_job(
            f"{BACKFILL_JOB}.running", now=NOW.replace(tzinfo=None), every=3600
        )
        await db.commit()
    assert await first.backfill() is None


@pytest.mark.asyncio
async def test_the_purge_runs_daily_and_keeps_the_rollups(sessions) -> None:
    clock = {"now": NOW}
    jobs = AnalyticsJobs(sessions, now=lambda: clock["now"])
    async with sessions() as db:
        from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import AnalyticsRollups

        port = jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db)
        rollups = AnalyticsRollups(port, now=lambda: clock["now"] - timedelta(days=50))
        await rollups.apply([payload("old", at=NOW - timedelta(days=50))])
        await db.commit()
    assert await jobs.purge() == 1
    assert await jobs.purge() is None  # once a day
    assert await _count(sessions, AnalyticsEventModel) == 0
    assert await _hourly_total(sessions) == 1
    clock["now"] = NOW + timedelta(days=1, minutes=1)
    assert await jobs.purge() == 0


@pytest.mark.asyncio
async def test_without_a_log_the_jobs_only_backfill_and_purge(sessions) -> None:
    jobs = AnalyticsJobs(sessions, legacy=FakeLegacy([payload("legacy")]))
    assert await jobs.drain() == 0
    assert await jobs.backfill() == 1
    assert CONSUMER_ID == "nexus.analytics.rollups"


@pytest.mark.asyncio
async def test_batches_two_processes_lost_are_healed(sessions, events, monkeypatch) -> None:
    """Two processes each read a batch and fail to write it. The first cannot move the
    cursor back (the second read past it), the second can: the heal replays the
    log's recent events, so the first batch is counted too."""
    monkeypatch.setattr(jobs_module, "BATCH", 2)
    first = AnalyticsJobs(sessions, events=events)
    second = AnalyticsJobs(sessions, events=events)
    for index in range(4):
        publish(events, payload(f"e-{index}"))
    batch_a = first._claim()
    batch_b = second._claim()
    first._rewind(batch_a)  # another process read past a: left where it is
    second._rewind(batch_b)  # cursor still at the end of b: moved back to a's end
    assert await first.drain() == 2  # b again
    assert await _hourly_total(sessions) == 2
    assert await first.heal() == 2  # a, from the log's last hours
    assert await second.heal() is None  # one process per period
    assert await _hourly_total(sessions) == 4


@pytest.mark.asyncio
async def test_messages_are_indexed_once_by_one_process(sessions) -> None:
    jobs = AnalyticsJobs(sessions)
    assert await jobs.index_messages() == 0
    assert await jobs.index_messages() is None


@pytest.mark.asyncio
async def test_a_failed_batch_is_handed_back_off_the_event_loop(
    sessions, events, monkeypatch
) -> None:
    """A failing write with a slow log must not freeze the API's loop meanwhile."""
    import asyncio
    import time as clock

    jobs = AnalyticsJobs(sessions, events=events)
    publish(events, payload("e-1"))

    async def broken(self, payloads):
        raise RuntimeError("database down")

    def slow_rewind(records) -> None:
        clock.sleep(0.5)

    async def silent() -> bool:
        return False

    monkeypatch.setattr(jobs, "_database_answers", silent)
    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply", broken)
    monkeypatch.setattr(jobs, "_rewind", slow_rewind)
    ticked = []

    async def tick() -> None:
        await asyncio.sleep(0.05)
        ticked.append(clock.monotonic())

    ticker = asyncio.create_task(tick())
    with pytest.raises(jobs_module.Unavailable):
        await jobs.drain()
    done = clock.monotonic()
    await ticker
    assert ticked and ticked[0] < done - 0.2


@pytest.mark.asyncio
async def test_the_legacy_files_are_deleted_once_after_the_backfill(sessions, events) -> None:
    clock = {"now": NOW}
    legacy = FakeLegacy([payload("legacy")])
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy, now=lambda: clock["now"])
    assert await jobs.clean_legacy_storage() is None  # the backfill has not run
    assert legacy.deleted == 0

    assert await jobs.backfill() == 1
    # A rolling deploy's old processes may still rewrite the aggregates for a while.
    clock["now"] = NOW + jobs_module.LEGACY_CLEANUP_DELAY - timedelta(minutes=1)
    assert await jobs.clean_legacy_storage() is None
    assert legacy.deleted == 0
    clock["now"] = NOW + jobs_module.LEGACY_CLEANUP_DELAY
    assert await jobs.clean_legacy_storage() == 1
    assert await jobs.clean_legacy_storage() is None  # recorded as done
    other = AnalyticsJobs(
        sessions, events=events, legacy=FakeLegacy([payload("x")]), now=lambda: clock["now"]
    )
    assert await other.clean_legacy_storage() is None  # in every process
    assert legacy.deleted == 1


@pytest.mark.asyncio
async def test_unreadable_legacy_files_are_neither_backfilled_nor_deleted(sessions, events) -> None:
    legacy = FakeLegacy([payload("legacy")], readable=False)
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy)
    with pytest.raises(ConnectionError):
        await jobs.backfill()
    assert await jobs.clean_legacy_storage() is None
    assert legacy.deleted == 0
    async with sessions() as db:
        port = jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db)
        assert await port.job_last_run(BACKFILL_JOB) is None


@pytest.mark.asyncio
async def test_a_failed_backfill_is_retried_at_upkeep_once_its_claim_lapses(
    sessions, events
) -> None:
    clock = {"now": NOW}
    publish(events, payload("logged"))
    legacy = FakeLegacy([payload("legacy")], readable=False)
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy, now=lambda: clock["now"])

    async def backfilled() -> bool:
        async with sessions() as db:
            port = jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db)
            return await port.job_last_run(BACKFILL_JOB) is not None

    await jobs.upkeep()  # the storage is unreachable: the backfill fails
    assert not await backfilled()
    legacy.readable = True
    clock["now"] = NOW + timedelta(minutes=10)
    await jobs.upkeep()  # the failed run's claim still holds
    assert not await backfilled()
    clock["now"] = NOW + timedelta(hours=1, minutes=1)
    await jobs.upkeep()  # without a restart
    assert await backfilled()
    async with sessions() as db:
        rows = (await db.execute(select(AnalyticsEventModel))).scalars().all()
    assert sorted(json.loads(r.payload)["event_id"] for r in rows) == ["legacy", "logged"]
    clock["now"] += jobs_module.LEGACY_CLEANUP_DELAY
    await jobs.upkeep()
    assert legacy.deleted == 1


@pytest.mark.asyncio
async def test_the_loop_starts_with_the_upkeep_then_drains(sessions, events, monkeypatch) -> None:
    calls: list[str] = []
    jobs = AnalyticsJobs(sessions, events=events)

    async def upkeep() -> None:
        calls.append("upkeep")

    async def drain() -> int:
        calls.append("drain")
        if calls.count("drain") == 2:
            raise asyncio.CancelledError
        return 0

    monkeypatch.setattr(jobs, "upkeep", upkeep)
    monkeypatch.setattr(jobs, "drain", drain)
    with pytest.raises(asyncio.CancelledError):
        await jobs.run(every=0)
    # The upkeep (the backfill first) before the first drain, then every few minutes.
    assert calls == ["upkeep", "drain", "drain"]


@pytest.mark.asyncio
async def test_a_cleanup_another_process_started_is_left_to_it(sessions, events) -> None:
    later = NOW + jobs_module.LEGACY_CLEANUP_DELAY
    legacy = FakeLegacy([])
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy)
    assert await jobs.backfill() == 0
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy, now=lambda: later)
    async with sessions() as db:
        port = jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db)
        assert await port.claim_job(
            f"{jobs_module.LEGACY_CLEANUP_JOB}.running",
            now=later.replace(tzinfo=None),
            every=3600,
        )
        await db.commit()
    assert await jobs.clean_legacy_storage() is None
    assert legacy.deleted == 0


@pytest.mark.asyncio
async def test_without_object_storage_there_is_nothing_to_clean(sessions, events) -> None:
    jobs = AnalyticsJobs(sessions, events=events)
    assert await jobs.backfill() == 0
    assert await jobs.clean_legacy_storage() is None


# -- poison events --------------------------------------------------------------


async def _event_ids(sessions) -> list[str]:
    async with sessions() as db:
        rows = (await db.execute(select(AnalyticsEventModel))).scalars().all()
    return sorted(json.loads(r.payload)["event_id"] for r in rows)


@pytest.mark.asyncio
async def test_one_malformed_event_never_stalls_the_consumer(sessions, events) -> None:
    """The audit's repro: an offset timestamp whose UTC value overflows (accepted by
    the log), then a NUL in a text column (refused by PostgreSQL), then valid events:
    one drain applies the valid ones, the cursor moves on, the heal works."""
    jobs = AnalyticsJobs(sessions, events=events)
    bad = payload("evil")
    bad["timestamp"] = "9999-12-31T23:30:00-05:00"
    publish(events, bad)
    nul = payload("nul")
    nul["event_name"] = "page\u0000viewed"
    nul["page_path"] = "/workspace/ws-1/\u0000home"
    publish(events, nul)
    for i in range(3):
        publish(events, payload(f"good-{i}", at=NOW - timedelta(minutes=i)))

    assert await jobs.drain() == 5
    assert await _event_ids(sessions) == ["good-0", "good-1", "good-2", "nul"]
    async with sessions() as db:
        paths = (await db.execute(select(AnalyticsEventModel.page_path))).scalars().all()
    assert "/workspace/ws-1/home" in paths and all("\x00" not in p for p in paths)
    assert await jobs.drain() == 0  # nothing left behind the cursor
    assert await jobs.heal() == 0  # replays the same events without failing


@pytest.mark.asyncio
async def test_an_event_the_rollups_refuse_is_skipped_and_the_rest_applied(
    sessions, events, monkeypatch, caplog
) -> None:
    """Whatever makes one event fail while the database answers: the batch is applied
    one event at a time, that event is skipped (and logged), the others are kept, in
    the consumer, the heal and the backfill alike."""
    monkeypatch.setattr(jobs_module, "BATCH", 3)
    original = jobs_module.AnalyticsSecondaryAdapterPostgresEvents.apply_events

    async def refuse_poison(self, recorded, *, not_before):
        if any(r.event_id == "poison" for r in recorded):
            raise ValueError("the rollups refuse it")
        return await original(self, recorded, not_before=not_before)

    monkeypatch.setattr(
        jobs_module.AnalyticsSecondaryAdapterPostgresEvents, "apply_events", refuse_poison
    )
    jobs = AnalyticsJobs(sessions, events=events, legacy=FakeLegacy([]))
    publish(events, payload("a"))
    publish(events, payload("poison"))
    publish(events, payload("b"))
    publish(events, payload("c"))
    with caplog.at_level(logging.WARNING, logger=jobs_module.logger.name):
        assert await jobs.drain() == 4
    assert await _event_ids(sessions) == ["a", "b", "c"]
    assert "1 event(s) skipped, the rollups refuse them: 'poison'" in caplog.text
    assert jobs.skipped_events == 1
    assert await jobs.heal() == 0
    assert await jobs.backfill() == 0  # done, not stuck on the same event
    async with sessions() as db:
        port = jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db)
        assert await port.job_last_run(BACKFILL_JOB) is not None


@pytest.mark.asyncio
async def test_events_past_tomorrow_are_not_applied(sessions, events) -> None:
    jobs = AnalyticsJobs(sessions, events=events)
    publish(events, payload("future", at=NOW + timedelta(days=2)))
    publish(events, payload("soon", at=NOW + timedelta(hours=2)))
    assert await jobs.drain() == 2
    assert await _event_ids(sessions) == ["soon"]


@pytest.mark.asyncio
async def test_a_step_that_keeps_failing_keeps_being_logged(sessions, monkeypatch, caplog) -> None:
    clock = {"t": 1000.0}
    monkeypatch.setattr(jobs_module.time, "monotonic", lambda: clock["t"])
    jobs = AnalyticsJobs(sessions)

    async def broken() -> None:
        raise RuntimeError("down")

    async def works() -> None:
        return None

    with caplog.at_level(logging.INFO, logger=jobs_module.logger.name):
        for _ in range(3):  # every 5 s: said once
            await jobs._step("rollups", broken)
            clock["t"] += 5
        assert caplog.text.count("rollups failed") == 1
        assert "still failing" not in caplog.text
        clock["t"] += jobs_module.FAILING_LOG_SECONDS
        await jobs._step("rollups", broken)
        assert "rollups still failing (4 times in a row)" in caplog.text
        await jobs._step("rollups", works)
        assert "rollups works again" in caplog.text


# -- legacy history ---------------------------------------------------------------


@pytest.mark.asyncio
async def test_nothing_is_deleted_that_was_not_replayed(sessions, events) -> None:
    """Every legacy event goes to the rollups whatever its age before its file is
    deleted; one that cannot be replayed is set aside, never deleted; replaying twice
    (backfill, then cleanup) counts each once; files an old process wrote after the
    backfill are replayed by the cleanup before it deletes them."""
    clock = {"now": NOW}
    old = payload("old", at=NOW - timedelta(days=60))
    legacy = FakeLegacy([payload("recent"), old, None, {"not": "an event"}])
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy, now=lambda: clock["now"])
    assert await jobs.backfill() == 2
    assert await _hourly_total(sessions) == 2
    assert await _event_ids(sessions) == ["recent"]  # "old" is past the raw retention

    # A rolling deploy's old process writes one more event after the backfill.
    legacy.add("late.json", payload("late", at=NOW + timedelta(minutes=5)))
    clock["now"] = NOW + jobs_module.LEGACY_CLEANUP_DELAY
    assert await jobs.clean_legacy_storage() == 3
    assert sorted(legacy.gone) == ["f0.json", "f1.json", "late.json"]
    assert sorted(legacy.aside) == ["f2.json", "f3.json"]
    assert legacy.files == {}
    assert await _hourly_total(sessions) == 3  # old and recent once, late too
    assert await _event_ids(sessions) == ["late", "recent"]


@pytest.mark.asyncio
async def test_a_legacy_event_refused_by_the_rollups_is_set_aside(
    sessions, events, monkeypatch
) -> None:
    original = jobs_module.AnalyticsSecondaryAdapterPostgresEvents.apply_legacy_events

    async def refuse_poison(self, recorded, *, raw_since):
        if any(r.event_id == "poison" for r in recorded):
            raise ValueError("the rollups refuse it")
        return await original(self, recorded, raw_since=raw_since)

    monkeypatch.setattr(
        jobs_module.AnalyticsSecondaryAdapterPostgresEvents,
        "apply_legacy_events",
        refuse_poison,
    )
    clock = {"now": NOW}
    legacy = FakeLegacy([payload("a"), payload("poison"), payload("b")])
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy, now=lambda: clock["now"])
    assert await jobs.backfill() == 2
    clock["now"] = NOW + jobs_module.LEGACY_CLEANUP_DELAY
    assert await jobs.clean_legacy_storage() == 2
    assert legacy.aside == ["f1.json"]
    assert sorted(legacy.gone) == ["f0.json", "f2.json"]


@pytest.mark.asyncio
async def test_a_database_outage_skips_nothing_and_deletes_nothing(
    sessions, events, monkeypatch
) -> None:
    clock = {"now": NOW}
    legacy = FakeLegacy([payload("a")])
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy, now=lambda: clock["now"])
    assert await jobs.backfill() == 1
    clock["now"] = NOW + jobs_module.LEGACY_CLEANUP_DELAY
    legacy.add("b.json", payload("b"))

    async def broken(self, payloads):
        raise RuntimeError("database down")

    async def silent() -> bool:
        return False

    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply_legacy", broken)
    monkeypatch.setattr(jobs, "_database_answers", silent)
    with pytest.raises(jobs_module.Unavailable):
        await jobs.clean_legacy_storage()
    assert legacy.deleted == 0 and legacy.aside == []
    async with sessions() as db:
        port = jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db)
        assert await port.job_last_run(jobs_module.LEGACY_CLEANUP_JOB) is None


# -- message facts written by a rolling deploy's old processes ----------------------


@pytest.mark.asyncio
async def test_messages_written_after_the_first_pass_get_their_facts(sessions) -> None:
    clock = {"now": NOW}
    jobs = AnalyticsJobs(sessions, now=lambda: clock["now"])
    assert await jobs.index_messages() == 0
    assert await jobs.recheck_messages() is None  # not due yet

    # An old process (no facts kept) writes a message after the first pass.
    later = (NOW + timedelta(minutes=10)).replace(tzinfo=None)
    async with sessions() as db:
        db.add(
            ConversationModel(
                id="conv-1",
                workspace_id="ws-1",
                user_id="alice",
                title="T",
                agent="aia",
                created_at=later,
                updated_at=later,
            )
        )
        await db.flush()
        db.add(
            MessageModel(
                id="m-1",
                conversation_id="conv-1",
                role="assistant",
                content="hi",
                created_at=later,
                metadata_=json.dumps({"steps": [{"tool_name": "search"}], "feedback": "like"}),
            )
        )
        await db.commit()

    clock["now"] = NOW + jobs_module.MESSAGE_FACTS_RECHECK_DELAY
    assert await jobs.recheck_messages() == 1
    assert await jobs.recheck_messages() is None  # once
    async with sessions() as db:
        tools = (await db.execute(select(MessageToolModel.tool_name))).scalars().all()
        feedback = (await db.execute(select(MessageModel.feedback))).scalars().all()
    assert tools == ["search"] and feedback == ["like"]


# -- page titles ------------------------------------------------------------------


@pytest.mark.asyncio
async def test_a_page_title_is_kept_per_organization_and_workspace(sessions) -> None:
    async with sessions() as db:
        from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import AnalyticsRollups

        rollups = AnalyticsRollups(
            jobs_module.AnalyticsSecondaryAdapterPostgresEvents(db), now=lambda: NOW
        )
        mine = {**payload("mine"), "page_title": "Home", "organization_id": "org-a"}
        spoof = {
            **payload("spoof"),
            "page_title": "Session expired, sign in at evil.example",
            "workspace_id": "ws-other",
            "organization_id": "org-b",
            "user_id": "mallory",
        }
        await rollups.apply([mine, spoof])
        await db.commit()
        rows = (
            await db.execute(
                select(
                    AnalyticsPageModel.organization_id,
                    AnalyticsPageModel.workspace_id,
                    AnalyticsPageModel.page_title,
                )
            )
        ).all()
    assert sorted(rows) == [
        ("org-a", "ws-1", "Home"),
        ("org-b", "ws-other", "Session expired, sign in at evil.example"),
    ]
