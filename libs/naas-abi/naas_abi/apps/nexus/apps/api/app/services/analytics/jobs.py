"""The analytics rollups' background work, run by every API process.

* **Consumer.** Every ``DRAIN_SECONDS`` the log's pending ``AnalyticsEventRecorded``
  are read through the one consumer cursor (``rollups.CONSUMER_ID``,
  ``iter_query_for_consumer``) and applied to the rollups. The cursor hands each
  batch to one process; applying is idempotent, so a batch whose write fails is
  handed out again (the cursor is moved back before it) without double counting.
* **Backfill** (once, ``rollups.BACKFILL_JOB``): what the log and the legacy
  object-storage events hold of the last 45 days, the organization stamped from the
  workspace. Then the messages of the last 45 days get their facts
  (``MESSAGE_FACTS_JOB``).
* **Legacy cleanup** (once, ``LEGACY_CLEANUP_JOB``, ``LEGACY_CLEANUP_DELAY`` after the
  backfill, asked at each upkeep): the removed analytics app's files under
  ``naas_abi/nexus/analytics/`` are deleted (``legacy_storage``). The delay outlasts a
  rolling deploy, whose old processes may still rewrite the app's aggregates.
* **Heal** (every 10 minutes across processes): the log's last six hours are applied
  again, so a batch a killed process read but never wrote is counted after all.
* **Purge** (daily across processes): the raw events past 45 days; the rollups stay.

Housekeeping for no user: the work runs as Nexus's ``api`` service account.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime, timedelta
from functools import partial
from itertools import islice
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.legacy_storage import (
    LegacyAnalyticsStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import (
    BACKFILL_JOB,
    CONSUMER_ID,
    RETENTION_DAYS,
    AnalyticsRollups,
    parse_timestamp,
    payload_of_log_event,
)
from naas_abi_core.engine.call_context import as_service_account

logger = logging.getLogger(__name__)

DRAIN_SECONDS = 5.0
BATCH = 500
MESSAGE_FACTS_JOB = "message_facts_v1"
LEGACY_CLEANUP_JOB = "legacy_storage_cleanup_v1"
LEGACY_CLEANUP_DELAY = timedelta(minutes=30)
HEAL_JOB = "heal_recent"
HEAL_SECONDS = 600.0
HEAL_WINDOW = timedelta(hours=6)
UPKEEP_SECONDS = 300.0

SessionFactory = Callable[[], Any]


class LegacyFiles(Protocol):
    """The removed app's object-storage files (``legacy_storage.LegacyAnalyticsStorage``)."""

    def list_events(self) -> list[dict[str, Any]]: ...

    def delete_all(self) -> int: ...


def _as_api(work: Callable[[], Any]) -> Any:
    with as_service_account("api"):
        return work()


class AnalyticsJobs:
    def __init__(
        self,
        sessions: SessionFactory,
        events: Any | None = None,
        legacy: LegacyFiles | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """``sessions``: an async session factory (``AsyncSessionLocal``); ``events``:
        the engine's EventService, None on a deploy with no log (the ingest then
        applies its events itself); ``legacy``: the removed app's object-storage
        files (their events read once by the backfill, then all deleted)."""
        self._sessions = sessions
        self._events = events
        self._legacy = legacy
        self._now = now or (lambda: datetime.now(UTC))
        self._failing: dict[str, int] = {}

    def _rollups(self, db: Any) -> AnalyticsRollups:
        return AnalyticsRollups(AnalyticsSecondaryAdapterPostgresEvents(db), now=self._now)

    # -- consumer ----------------------------------------------------------------

    def _claim(self) -> list[Any]:
        assert self._events is not None
        return list(
            self._events.iter_query_for_consumer(
                CONSUMER_ID, AnalyticsEventRecorded, limit=BATCH, batch_size=BATCH
            )
        )

    def _rewind(self, records: list[Any]) -> None:
        """Hand a batch out again: the cursor back before its first event, unless
        another process read past the batch since (moving it back would skip what
        that one read; ``heal`` replays both)."""
        assert self._events is not None
        seqs = [s for s in (getattr(r, "_seq", None) for r in records) if isinstance(s, int)]
        if not seqs:
            return
        event_type = str(AnalyticsEventRecorded._class_uri)
        if self._events.get_cursor(CONSUMER_ID, event_type) == max(seqs):
            self._events.set_cursor(CONSUMER_ID, event_type, min(seqs) - 1)

    def _rewind_quietly(self, records: list[Any]) -> None:
        try:
            _as_api(partial(self._rewind, records))
        except Exception:  # noqa: BLE001 - ``heal`` replays the batch
            logger.warning("[analytics] the cursor was not moved back", exc_info=True)

    async def drain(self) -> int:
        """Apply what the log holds past the cursor; returns how many events were read."""
        if self._events is None:
            return 0
        read = 0
        while True:
            records = await asyncio.to_thread(_as_api, self._claim)
            if not records:
                return read
            payloads = [p for p in map(payload_of_log_event, records) if p is not None]
            try:
                async with self._sessions() as db:
                    await self._rollups(db).apply(payloads)
                    await db.commit()
            except asyncio.CancelledError:
                # Shutdown: no await left, so in this thread.
                self._rewind_quietly(records)
                raise
            except Exception:
                # Off the event loop: the log may be slow too (an RPC per call).
                await asyncio.to_thread(self._rewind_quietly, records)
                raise
            read += len(records)
            if len(records) < BATCH:
                return read

    # -- backfill ----------------------------------------------------------------

    def _naive_now(self) -> datetime:
        return self._now().astimezone(UTC).replace(tzinfo=None)

    def _cutoff(self) -> datetime:
        return self._now().astimezone(UTC).replace(tzinfo=None) - timedelta(days=RETENTION_DAYS)

    async def _log_batches(
        self, since_moment: datetime | None = None
    ) -> AsyncIterator[list[dict[str, Any]]]:
        """The log's tracker payloads stored since ``since_moment`` (naive UTC; the
        retention cutoff by default)."""
        if self._events is None:
            return
        since = (since_moment or self._cutoff()).replace(tzinfo=UTC).isoformat()
        stream: Iterator[Any] | None = None

        events = self._events

        def pull() -> list[Any]:
            nonlocal stream
            if stream is None:
                stream = events.iter_query(
                    AnalyticsEventRecorded, since_timestamp=since, batch_size=BATCH
                )
            return list(islice(stream, BATCH))

        while True:
            records = await asyncio.to_thread(_as_api, pull)
            if not records:
                return
            yield [p for p in map(payload_of_log_event, records) if p is not None]

    async def _legacy_batches(self) -> AsyncIterator[list[dict[str, Any]]]:
        if self._legacy is None:
            return
        # Unreadable storage raises: the backfill is then not recorded as done, so
        # the cleanup, which waits for it, never deletes events nobody replayed.
        found = await asyncio.to_thread(_as_api, self._legacy.list_events)
        cutoff = self._cutoff()
        recent = [
            e
            for e in found
            if isinstance(e, dict)
            and (moment := parse_timestamp(e.get("timestamp"))) is not None
            and moment >= cutoff
        ]
        for index in range(0, len(recent), BATCH):
            yield recent[index : index + BATCH]

    async def _batches(self) -> AsyncIterator[list[dict[str, Any]]]:
        # The legacy files first: if the storage cannot be read, the backfill stops
        # before replaying the log.
        async for batch in self._legacy_batches():
            yield batch
        async for batch in self._log_batches():
            yield batch

    async def backfill(self) -> int | None:
        """Once: the log and the legacy events of the last 45 days. None when done
        already or being done by another process."""
        async with self._sessions() as db:
            rollups = self._rollups(db)
            claimed = await rollups.claim_backfill()
            await db.commit()
            if not claimed:
                return None
            applied = await rollups.backfill(self._batches(), commit=db.commit)
            await db.commit()
        logger.info("[analytics] backfill applied %d events", applied)
        return applied

    async def index_messages(self) -> int | None:
        """Once: the facts of the messages of the last 45 days (written before the
        chat adapter kept them)."""
        from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.message_facts import (  # noqa: E501
            index_message_facts,
        )

        async with self._sessions() as db:
            port = AnalyticsSecondaryAdapterPostgresEvents(db)
            if await port.job_last_run(MESSAGE_FACTS_JOB) is not None:
                return None
            # One process at a time (another takes over an hour after one that died).
            claimed = await port.claim_job(
                f"{MESSAGE_FACTS_JOB}.running", now=self._naive_now(), every=3600.0
            )
            await db.commit()
            if not claimed:
                return None
            done = await index_message_facts(db, self._cutoff())
            await port.record_job_run(MESSAGE_FACTS_JOB, self._naive_now())
            await db.commit()
        return done

    # -- legacy cleanup ----------------------------------------------------------

    async def clean_legacy_storage(self) -> int | None:
        """Once, ``LEGACY_CLEANUP_DELAY`` after the backfill: delete the removed app's
        object-storage files (its aggregates and raw events). The delay lets a rolling
        deploy finish: its old processes rebuild the app's aggregates until they stop.
        How many objects went; None when there is no object storage, the backfill is
        not done or too recent, the cleanup is done already or another process is
        doing it."""
        if self._legacy is None:
            return None
        async with self._sessions() as db:
            port = AnalyticsSecondaryAdapterPostgresEvents(db)
            if await port.job_last_run(LEGACY_CLEANUP_JOB) is not None:
                return None
            backfilled = await port.job_last_run(BACKFILL_JOB)
            if backfilled is None or backfilled > self._naive_now() - LEGACY_CLEANUP_DELAY:
                return None
            # One process at a time (another takes over an hour after one that died).
            claimed = await port.claim_job(
                f"{LEGACY_CLEANUP_JOB}.running", now=self._naive_now(), every=3600.0
            )
            await db.commit()
            if not claimed:
                return None
            deleted = await asyncio.to_thread(_as_api, self._legacy.delete_all)
            await port.record_job_run(LEGACY_CLEANUP_JOB, self._naive_now())
            await db.commit()
        logger.info("[analytics] deleted %d legacy analytics files from object storage", deleted)
        return deleted

    # -- heal --------------------------------------------------------------------

    async def heal(self) -> int | None:
        """Every ``HEAL_SECONDS`` across processes: replay the log's last
        ``HEAL_WINDOW`` (idempotent), so a batch a process read but never wrote
        (killed between the two) is counted after all. None when not this
        process's turn."""
        if self._events is None:
            return None
        async with self._sessions() as db:
            port = AnalyticsSecondaryAdapterPostgresEvents(db)
            claimed = await port.claim_job(HEAL_JOB, now=self._naive_now(), every=HEAL_SECONDS)
            await db.commit()
            if not claimed:
                return None
            rollups = self._rollups(db)
            applied = 0
            async for batch in self._log_batches(self._naive_now() - HEAL_WINDOW):
                applied += await rollups.apply(batch)
                await db.commit()
        if applied:
            logger.info("[analytics] heal applied %d events the consumer had missed", applied)
        return applied

    # -- purge -------------------------------------------------------------------

    async def purge(self) -> int | None:
        async with self._sessions() as db:
            purged = await self._rollups(db).purge()
            await db.commit()
        if purged:
            logger.info(
                "[analytics] purged %d raw events older than %d days", purged, RETENTION_DAYS
            )
        return purged

    # -- the loop ----------------------------------------------------------------

    async def _step(self, name: str, work: Callable[[], Any]) -> None:
        try:
            await work()
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - retried at the next tick or start
            # Said once per run of failures, not every tick.
            failing = self._failing.get(name, 0)
            self._failing[name] = failing + 1
            if failing == 0:
                logger.warning("[analytics] %s failed", name, exc_info=True)
            return
        if self._failing.pop(name, 0):
            logger.info("[analytics] %s works again", name)

    async def run(self, *, every: float = DRAIN_SECONDS) -> None:
        await self._step("backfill", self.backfill)
        await self._step("message facts", self.index_messages)
        next_upkeep = 0.0
        while True:
            await self._step("rollups", self.drain)
            if time.monotonic() >= next_upkeep:
                # The purge and the heal are claimed across processes; each process
                # asks every few minutes, not every tick.
                await self._step("heal", self.heal)
                await self._step("purge", self.purge)
                await self._step("legacy cleanup", self.clean_legacy_storage)
                next_upkeep = time.monotonic() + UPKEEP_SECONDS
            await asyncio.sleep(every)


_task: asyncio.Task[None] | None = None


def start_analytics_jobs(sessions: SessionFactory) -> asyncio.Task[None] | None:
    """Start the jobs in this process, with the engine's event log and object storage
    when it has them. Idempotent."""
    global _task
    if _task is not None and not _task.done():
        return _task
    events = None
    legacy = None
    try:
        from naas_abi import ABIModule

        engine = ABIModule.get_instance().engine
        if engine.services.events_available():
            events = engine.services.events
        legacy = LegacyAnalyticsStorage(engine.services.object_storage)
    except Exception:  # noqa: BLE001 - standalone Nexus: rollups from direct ingest only
        logger.info("[analytics] no engine: the rollups follow direct ingests only")
    jobs = AnalyticsJobs(sessions, events=events, legacy=legacy)
    with as_service_account("api"):
        _task = asyncio.get_running_loop().create_task(jobs.run())
    return _task


def stop_analytics_jobs() -> None:
    """Cancel this process's jobs (shutdown): a batch being written is handed out again."""
    global _task
    if _task is not None and not _task.done():
        _task.cancel()
    _task = None
