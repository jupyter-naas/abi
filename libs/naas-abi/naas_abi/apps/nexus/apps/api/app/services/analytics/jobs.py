"""The analytics rollups' background work, run by every API process.

* **Consumer.** Every ``DRAIN_SECONDS`` the log's pending ``AnalyticsEventRecorded``
  are read through the one consumer cursor (``rollups.CONSUMER_ID``,
  ``iter_query_for_consumer``) and applied to the rollups. The cursor hands each
  batch to one process; applying is idempotent, so a batch whose write fails because
  the database does is handed out again (the cursor is moved back before it) without
  double counting.
* **Poison events.** A batch that fails while the database answers is applied again
  event by event (``_apply_isolated``): the events that fail alone are skipped and
  logged, the others are applied, and the cursor moves on. No event a client sends can
  stall the consumer, the heal or the backfill.
* **Backfill** (once, ``rollups.BACKFILL_JOB``): every event the legacy object storage
  holds, whatever its age (rollups only past 45 days), then what the log holds of the
  last 45 days, the organization stamped from the workspace. Then the messages of the
  last 45 days get their facts (``MESSAGE_FACTS_JOB``), and the messages written since
  that run started get them again ``MESSAGE_FACTS_RECHECK_DELAY`` later
  (``MESSAGE_FACTS_RECHECK_JOB``: a rolling deploy's old processes write messages
  without their facts until they stop). Each is asked at each upkeep until recorded
  as done: a failed run is retried once its claim lapses (an hour).
* **Legacy cleanup** (once, ``LEGACY_CLEANUP_JOB``, ``LEGACY_CLEANUP_DELAY`` after the
  backfill, asked at each upkeep): the legacy events are replayed again (idempotent:
  what a rolling deploy's old processes wrote since the backfill is counted too), then
  the removed app's files under ``naas_abi/nexus/analytics/`` are deleted, each raw
  event only once it was replayed; the ones that could not be (unreadable, not an
  event, refused by the rollups) are moved under ``unreadable/`` and logged
  (``legacy_storage``). The delay outlasts a rolling deploy, whose old processes may
  still rewrite the app's aggregates.
* **Heal** (every 10 minutes across processes): the log's last six hours are applied
  again, so a batch a killed process read but never wrote is counted after all.
* **Purge** (daily across processes): the raw events past 45 days; the rollups stay.

A step that keeps failing is logged when it starts failing, then every
``FAILING_LOG_SECONDS`` with the count, and once when it works again.

Housekeeping for no user: the work runs as Nexus's ``api`` service account.
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from datetime import UTC, datetime, timedelta
from functools import partial
from itertools import islice
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.legacy_storage import (
    LegacyAnalyticsStorage,
    LegacyEvent,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import (
    BACKFILL_JOB,
    CONSUMER_ID,
    RETENTION_DAYS,
    AnalyticsRollups,
    applicable,
    payload_of_log_event,
)
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import text

logger = logging.getLogger(__name__)

DRAIN_SECONDS = 5.0
BATCH = 500
MESSAGE_FACTS_JOB = "message_facts_v1"
MESSAGE_FACTS_RECHECK_JOB = "message_facts_v2"
MESSAGE_FACTS_RECHECK_DELAY = timedelta(minutes=30)
# Messages since a little before the first pass started (clocks of processes differ).
MESSAGE_FACTS_RECHECK_MARGIN = timedelta(minutes=10)
LEGACY_CLEANUP_JOB = "legacy_storage_cleanup_v1"
LEGACY_CLEANUP_DELAY = timedelta(minutes=30)
HEAL_JOB = "heal_recent"
HEAL_SECONDS = 600.0
HEAL_WINDOW = timedelta(hours=6)
UPKEEP_SECONDS = 300.0
FAILING_LOG_SECONDS = 600.0

SessionFactory = Callable[[], Any]


class LegacyFiles(Protocol):
    """The removed app's object-storage files (``legacy_storage.LegacyAnalyticsStorage``)."""

    def list_events(self) -> list[LegacyEvent]: ...

    def delete_replayed(self, names: list[str]) -> int: ...

    def set_aside(self, names: list[str]) -> int: ...


Apply = Callable[[AnalyticsRollups, list[dict[str, Any]]], Awaitable[int]]


class Unavailable(RuntimeError):
    """The database failed and does not answer: a batch is handed out again, never
    skipped."""


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
        # step -> (failures in a row, when it was last logged)
        self._failing: dict[str, tuple[int, float]] = {}
        # Events the rollups refused (skipped) since this process started.
        self.skipped_events = 0

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

    # -- applying, the events the rollups refuse skipped ---------------------------

    async def _database_answers(self) -> bool:
        try:
            async with self._sessions() as db:
                await db.execute(text("SELECT 1"))
            return True
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the database is what failed
            return False

    async def _apply_in_session(self, apply: Apply, payloads: list[dict[str, Any]]) -> int:
        async with self._sessions() as db:
            applied = await apply(self._rollups(db), payloads)
            await db.commit()
        return applied

    async def _apply_isolated(
        self, payloads: list[dict[str, Any]], *, apply: Apply | None = None, what: str = "event"
    ) -> tuple[int, list[int]]:
        """Apply a batch of tracker payloads in one transaction; when it fails while the
        database answers, apply them one by one and skip the ones that fail alone.
        Returns how many were new and the indexes of the skipped ones; raises
        ``Unavailable`` when the database does not answer (nothing is skipped then)."""
        apply = apply or AnalyticsRollups.apply
        if not payloads:
            return 0, []
        try:
            return await self._apply_in_session(apply, payloads), []
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001 - told apart below
            if not await self._database_answers():
                raise Unavailable("the analytics database does not answer") from exc
            if len(payloads) > 1:
                logger.info("[analytics] a batch of %d failed; applied one by one", len(payloads))
        applied, skipped = 0, []
        first_error: Exception | None = None
        for index, payload in enumerate(payloads):
            for attempt in range(2):  # once more: a deadlock between processes passes
                try:
                    applied += await self._apply_in_session(apply, [payload])
                    break
                except asyncio.CancelledError:
                    raise
                except Exception as exc:  # noqa: BLE001 - told apart below
                    if not await self._database_answers():
                        raise Unavailable("the analytics database does not answer") from exc
                    if attempt == 1:
                        skipped.append(index)
                        first_error = first_error or exc
        if skipped:
            # One line per batch, however many: a flood of bad events is one warning.
            self.skipped_events += len(skipped)
            names = [
                str(payloads[i].get("event_id") if isinstance(payloads[i], dict) else None)[:80]
                for i in skipped[:5]
            ]
            logger.warning(
                "[analytics] %d %s(s) skipped, the rollups refuse them: %s%s (%s: %s); "
                "%d skipped since start",
                len(skipped),
                what,
                ", ".join(repr(n) for n in names),
                ", ..." if len(skipped) > len(names) else "",
                type(first_error).__name__,
                str(first_error)[:200],
                self.skipped_events,
            )
        return applied, skipped

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
                await self._apply_isolated(payloads)
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

    async def _replay_log(self, since_moment: datetime | None = None) -> int:
        applied = 0
        async for batch in self._log_batches(since_moment):
            applied += (await self._apply_isolated(batch))[0]
        return applied

    async def _replay_legacy(self) -> tuple[int, list[str], list[str]]:
        """Apply every legacy event, whatever its age (idempotent). Returns how many
        were new, the files replayed and those that could not be (unreadable, not an
        event, or refused by the rollups). Unreadable storage raises: nothing is then
        recorded as done, nor deleted."""
        if self._legacy is None:
            return 0, [], []
        found = await asyncio.to_thread(_as_api, self._legacy.list_events)
        now = self._now()
        replayable = [(name, e) for name, e in found if e is not None and applicable(e, now)]
        kept = [name for name, e in found if e is None or not applicable(e, now)]
        replayed: list[str] = []
        applied = 0
        for index in range(0, len(replayable), BATCH):
            batch = replayable[index : index + BATCH]
            new, skipped = await self._apply_isolated(
                [event for _, event in batch],
                apply=AnalyticsRollups.apply_legacy,
                what="legacy event",
            )
            applied += new
            refused = set(skipped)
            for position, (name, _) in enumerate(batch):
                (kept if position in refused else replayed).append(name)
        return applied, replayed, kept

    async def backfill(self) -> int | None:
        """Once: every legacy event (whatever its age), then the log's last 45 days.
        None when done already or being done by another process."""
        async with self._sessions() as db:
            claimed = await self._rollups(db).claim_backfill()
            await db.commit()
        if not claimed:
            return None
        # The legacy files first: if the storage cannot be read, the backfill stops
        # before replaying the log (and is not recorded as done).
        applied, _replayed, kept = await self._replay_legacy()
        applied += await self._replay_log()
        async with self._sessions() as db:
            await AnalyticsSecondaryAdapterPostgresEvents(db).record_job_run(
                BACKFILL_JOB, self._naive_now()
            )
            await db.commit()
        logger.info(
            "[analytics] backfill applied %d events (%d legacy files not replayable)",
            applied,
            len(kept),
        )
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

    async def recheck_messages(self) -> int | None:
        """Once, ``MESSAGE_FACTS_RECHECK_DELAY`` after the first pass: the facts of the
        messages written since that pass started (idempotent), so that those a rolling
        deploy's old processes wrote without their facts get them. None when not due."""
        from naas_abi.apps.nexus.apps.api.app.services.chat.adapters.secondary.message_facts import (  # noqa: E501
            index_message_facts,
        )

        async with self._sessions() as db:
            port = AnalyticsSecondaryAdapterPostgresEvents(db)
            if await port.job_last_run(MESSAGE_FACTS_RECHECK_JOB) is not None:
                return None
            first_done = await port.job_last_run(MESSAGE_FACTS_JOB)
            if first_done is None or first_done > self._naive_now() - MESSAGE_FACTS_RECHECK_DELAY:
                return None
            started = await port.job_last_run(f"{MESSAGE_FACTS_JOB}.running") or first_done
            claimed = await port.claim_job(
                f"{MESSAGE_FACTS_RECHECK_JOB}.running", now=self._naive_now(), every=3600.0
            )
            await db.commit()
            if not claimed:
                return None
            done = await index_message_facts(db, started - MESSAGE_FACTS_RECHECK_MARGIN)
            await port.record_job_run(MESSAGE_FACTS_RECHECK_JOB, self._naive_now())
            await db.commit()
        return done

    # -- legacy cleanup ----------------------------------------------------------

    async def clean_legacy_storage(self) -> int | None:
        """Once, ``LEGACY_CLEANUP_DELAY`` after the backfill: replay the legacy events
        again (what a rolling deploy's old processes wrote since the backfill), then
        delete the removed app's aggregates and each raw event that was replayed; the
        others are moved under ``unreadable/``, never deleted. How many objects were
        deleted; None when there is no object storage, the backfill is not done or too
        recent, the cleanup is done already or another process is doing it."""
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
        applied, replayed, kept = await self._replay_legacy()
        deleted = await asyncio.to_thread(_as_api, partial(self._legacy.delete_replayed, replayed))
        set_aside = (
            await asyncio.to_thread(_as_api, partial(self._legacy.set_aside, kept)) if kept else 0
        )
        async with self._sessions() as db:
            await AnalyticsSecondaryAdapterPostgresEvents(db).record_job_run(
                LEGACY_CLEANUP_JOB, self._naive_now()
            )
            await db.commit()
        logger.info(
            "[analytics] legacy analytics files: %d replayed again (%d new), %d deleted, "
            "%d not replayable kept under unreadable/ (%d moved)",
            len(replayed),
            applied,
            deleted,
            len(kept),
            set_aside,
        )
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
        applied = await self._replay_log(self._naive_now() - HEAL_WINDOW)
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
            # Said when it starts failing, then every FAILING_LOG_SECONDS, not every tick.
            failures, said = self._failing.get(name, (0, 0.0))
            now = time.monotonic()
            failures += 1
            if failures == 1:
                logger.warning("[analytics] %s failed", name, exc_info=True)
                said = now
            elif now - said >= FAILING_LOG_SECONDS:
                logger.warning(
                    "[analytics] %s still failing (%d times in a row)",
                    name,
                    failures,
                    exc_info=True,
                )
                said = now
            self._failing[name] = (failures, said)
            return
        if self._failing.pop(name, None):
            logger.info("[analytics] %s works again", name)

    async def upkeep(self) -> None:
        """What each process asks every ``UPKEEP_SECONDS`` (and first at start): the
        one-time jobs until they are recorded as done, so a failed backfill (storage or
        database unreachable) is retried once its claim lapses rather than at the next
        process start, while the log still holds what it replays; then the heal, the
        purge and the legacy cleanup. Each is claimed across processes, and a done
        one-time job costs one query."""
        await self._step("backfill", self.backfill)
        await self._step("message facts", self.index_messages)
        await self._step("message facts recheck", self.recheck_messages)
        await self._step("heal", self.heal)
        await self._step("purge", self.purge)
        await self._step("legacy cleanup", self.clean_legacy_storage)

    async def run(self, *, every: float = DRAIN_SECONDS) -> None:
        next_upkeep = 0.0
        while True:
            if time.monotonic() >= next_upkeep:
                await self.upkeep()
                next_upkeep = time.monotonic() + UPKEEP_SECONDS
            await self._step("rollups", self.drain)
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
