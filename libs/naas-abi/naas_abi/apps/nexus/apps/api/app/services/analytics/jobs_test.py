"""The rollups' background work: the log's consumer, the one-time backfill, the purge.

A real EventService on SQLite holds the log; the rollups are SQLite tables.
"""

from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime, timedelta

import pytest
import pytest_asyncio
from naas_abi.apps.nexus.apps.api.app.core.database import Base
from naas_abi.apps.nexus.apps.api.app.models import (
    AnalyticsEventModel,
    AnalyticsHourlyModel,
    AnalyticsSessionModel,
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
    """The removed app's object-storage files: its raw events, and whether they went."""

    def __init__(self, found: list[dict], *, readable: bool = True) -> None:
        self.found = found
        self.readable = readable
        self.deleted = 0

    def list_events(self) -> list[dict]:
        if not self.readable:
            raise ConnectionError("object storage unreachable")
        return [dict(e) for e in self.found]

    def delete_all(self) -> int:
        self.deleted += 1
        gone, self.found = len(self.found), []
        return gone


@pytest_asyncio.fixture
async def sessions(tmp_path):
    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'nexus.sqlite'}")
    async with engine.begin() as conn:
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

    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply", broken)
    with pytest.raises(RuntimeError):
        await jobs.drain()
    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply", original)
    assert await jobs.drain() == 2
    assert await _hourly_total(sessions) == 2


@pytest.mark.asyncio
async def test_the_backfill_replays_45_days_of_the_log_and_the_legacy_events_once(
    sessions, events
) -> None:
    # Two consumers' worth: what was logged before the rollups existed.
    publish(events, payload("logged"))
    legacy = [
        {**payload("legacy"), "user_email": "alice@example.com"},
        payload("too-old", at=NOW - timedelta(days=50)),
        {**payload("logged")},  # also in the log: counted once
        {"not": "an event"},
    ]
    jobs = AnalyticsJobs(sessions, events=events, legacy=FakeLegacy(legacy))
    assert await jobs.backfill() == 2
    assert await jobs.backfill() is None  # recorded as done

    async with sessions() as db:
        rows = (await db.execute(select(AnalyticsEventModel))).scalars().all()
    assert sorted(json.loads(r.payload)["event_id"] for r in rows) == ["legacy", "logged"]
    assert all("alice@example.com" not in r.payload for r in rows)
    # The consumer then reads the same log: nothing is counted twice.
    assert await jobs.drain() == 1
    assert await _hourly_total(sessions) == 2


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

    monkeypatch.setattr(jobs_module.AnalyticsRollups, "apply", broken)
    monkeypatch.setattr(jobs, "_rewind", slow_rewind)
    ticked = []

    async def tick() -> None:
        await asyncio.sleep(0.05)
        ticked.append(clock.monotonic())

    ticker = asyncio.create_task(tick())
    with pytest.raises(RuntimeError):
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
