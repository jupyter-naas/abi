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
* **Purge** (daily across processes): the raw events past 45 days; the rollups stay.

Housekeeping for no user: the work runs as Nexus's ``api`` service account.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime, timedelta
from functools import partial
from itertools import islice
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__postgres import (  # noqa: E501
    AnalyticsSecondaryAdapterPostgresEvents,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.rollups import (
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

SessionFactory = Callable[[], Any]


def _as_api(work: Callable[[], Any]) -> Any:
    with as_service_account("api"):
        return work()


class AnalyticsJobs:
    def __init__(
        self,
        sessions: SessionFactory,
        events: Any | None = None,
        legacy_events: Callable[[], list[dict[str, Any]]] | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        """``sessions``: an async session factory (``AsyncSessionLocal``); ``events``:
        the engine's EventService, None on a deploy with no log (the ingest then
        applies its events itself); ``legacy_events``: the object-storage events of
        the platform app (read once, by the backfill)."""
        self._sessions = sessions
        self._events = events
        self._legacy_events = legacy_events
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
        """Hand a batch out again: the cursor back before its first event."""
        assert self._events is not None
        seqs = [s for s in (getattr(r, "_seq", None) for r in records) if isinstance(s, int)]
        if seqs:
            self._events.set_cursor(
                CONSUMER_ID, str(AnalyticsEventRecorded._class_uri), min(seqs) - 1
            )

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
            except Exception:
                await asyncio.to_thread(_as_api, partial(self._rewind, records))
                raise
            read += len(records)
            if len(records) < BATCH:
                return read

    # -- backfill ----------------------------------------------------------------

    def _cutoff(self) -> datetime:
        return self._now().astimezone(UTC).replace(tzinfo=None) - timedelta(days=RETENTION_DAYS)

    async def _log_batches(self) -> AsyncIterator[list[dict[str, Any]]]:
        if self._events is None:
            return
        since = self._cutoff().replace(tzinfo=UTC).isoformat()
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
        if self._legacy_events is None:
            return
        try:
            found = await asyncio.to_thread(_as_api, self._legacy_events)
        except Exception:  # noqa: BLE001 - history is a nice-to-have
            logger.warning("[analytics] legacy events unreadable; not backfilled", exc_info=True)
            return
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
        async for batch in self._log_batches():
            yield batch
        async for batch in self._legacy_batches():
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
            done = await index_message_facts(db, self._cutoff())
            await port.record_job_run(MESSAGE_FACTS_JOB, self._cutoff())
            await db.commit()
        return done

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
        while True:
            await self._step("rollups", self.drain)
            await self._step("purge", self.purge)
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
        from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__object_storage import (  # noqa: E501
            AnalyticsSecondaryAdapterObjectStorage,
        )

        engine = ABIModule.get_instance().engine
        if engine.services.events_available():
            events = engine.services.events
        storage = AnalyticsSecondaryAdapterObjectStorage(
            object_storage=engine.services.object_storage
        )
        legacy = storage.list_events
    except Exception:  # noqa: BLE001 - standalone Nexus: rollups from direct ingest only
        logger.info("[analytics] no engine: the rollups follow direct ingests only")
    jobs = AnalyticsJobs(sessions, events=events, legacy_events=legacy)
    with as_service_account("api"):
        _task = asyncio.get_running_loop().create_task(jobs.run())
    return _task
