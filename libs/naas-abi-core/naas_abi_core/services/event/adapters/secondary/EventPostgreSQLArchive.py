"""Archive old events from the PostgreSQL event log into the Dataset Service.

Hourly, ``event_archive`` moves the events older than the retention window
(7 days by default) into the dataset ``events_archive``, in the namespace named
after the adapter's schema, partitioned by month. It then deletes them from
PostgreSQL. Archived events are read with SQL on the dataset; the event service
reads what is left in PostgreSQL. See
docs/adr/20261006_event-log-archive.md.

Exactly once: the archive's highest ``seq`` is where the last run stopped. A run
first deletes what an interrupted run archived but did not delete, then moves
the next batches, each written as one snapshot before its rows are deleted.

Never too early: archiving stops before the first event newer than the window,
and below the cursor of every consumer that read within the window. Consumers
idle longer than that are reported and left behind.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from typing import TYPE_CHECKING, Any

from naas_abi_core import logger
from naas_abi_core.module.jobs import Cron, JobContext, JobsMixin, job
from naas_abi_core.services.dataset.DatasetPort import (
    ColumnSpec,
    DatasetAlreadyExistsError,
    DatasetNotFoundError,
    DatasetSpec,
    PartitionSpec,
)
from naas_abi_core.services.event.EventPort import StoredEvent

if TYPE_CHECKING:
    from naas_abi_core.services.dataset.DatasetService import DatasetService
    from naas_abi_core.services.event.adapters.secondary.EventPostgreSQLAdapter import (
        EventPostgreSQLAdapter,
    )

EVENT_ARCHIVE_OWNER = "naas_abi_core.event_archive"
ARCHIVE_DATASET = "events_archive"


def archive_spec(namespace: str) -> DatasetSpec:
    return DatasetSpec(
        name=ARCHIVE_DATASET,
        namespace=namespace,
        columns=(
            ColumnSpec(name="seq", type="bigint"),
            ColumnSpec(name="id", type="string"),
            ColumnSpec(name="event_type", type="string"),
            # Kept exactly as the event log had it.
            ColumnSpec(name="timestamp", type="string"),
            # Its UTC date: the partition key.
            ColumnSpec(name="day", type="date"),
            # UTF-8 text, else base64 (payload_encoding).
            ColumnSpec(name="payload", type="string"),
            ColumnSpec(name="payload_encoding", type="string"),
        ),
        partitions=(PartitionSpec(column="day", transform="month"),),
        primary_key=("seq",),
    )


def _day(timestamp: str) -> date | None:
    try:
        moment = datetime.fromisoformat(timestamp)
    except ValueError:
        return None
    if moment.tzinfo is not None:
        moment = moment.astimezone(UTC)
    return moment.date()


def _archive_row(event: StoredEvent) -> dict[str, Any]:
    try:
        payload, encoding = event.payload.decode("utf-8"), "utf-8"
    except UnicodeDecodeError:
        payload, encoding = base64.b64encode(event.payload).decode("ascii"), "base64"
    return {
        "seq": event.seq,
        "id": event.id,
        "event_type": event.event_type,
        "timestamp": event.timestamp,
        "day": _day(event.timestamp),
        "payload": payload,
        "payload_encoding": encoding,
    }


@dataclass
class ArchiveReport:
    archived: int = 0
    batches: int = 0
    through: int = 0  # the archive's highest seq after the run
    idle_consumers: list[tuple[str, str]] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {
            "archived": self.archived,
            "batches": self.batches,
            "through": self.through,
            "idle_consumers": [list(c) for c in self.idle_consumers],
        }


class EventArchiveJobs(JobsMixin):
    _sync_jobs = True

    def __init__(
        self,
        events: EventPostgreSQLAdapter,
        datasets: DatasetService,
        *,
        namespace: str,
        retain: timedelta = timedelta(days=7),
        batch_rows: int = 10_000,
    ) -> None:
        self.events, self.datasets = events, datasets
        self.namespace = namespace
        self.retain, self.batch_rows = retain, batch_rows

    @job(
        "event_archive",
        triggers=(Cron("0 30 * * * *", time_zone="UTC"),),
        timeout=timedelta(hours=1),
    )
    def archive(self, ctx: JobContext) -> dict[str, Any]:
        """Move events older than the retention window to the Dataset Service."""
        report = self.run(ctx=ctx)
        for consumer_id, event_type in report.idle_consumers:
            ctx.log(f"Idle consumer {consumer_id} ({event_type}) left behind")
        ctx.log(f"Archived {report.archived} events, through seq {report.through}")
        return report.as_dict()

    def run(
        self, *, ctx: JobContext | None = None, now: datetime | None = None
    ) -> ArchiveReport:
        cutoff = (now or datetime.now(UTC)) - self.retain
        self._ensure_dataset()
        done = self._archived_through()
        # What an interrupted run archived but did not delete.
        self.events.remove_through(done)
        boundary = self.events.archivable_through(
            cutoff.isoformat(), consumers_active_since=cutoff
        )
        report = ArchiveReport(through=done, idle_consumers=boundary.idle_consumers)
        for consumer_id, event_type in boundary.idle_consumers:
            logger.warning(
                f"Archiving events that idle consumer {consumer_id} "
                f"({event_type}) has not read: it read nothing for {self.retain}"
            )
        while report.through < boundary.through:
            if ctx is not None and ctx.cancelled.is_set():
                break
            batch = self.events.query(
                since_seq=report.through,
                until_seq=boundary.through,
                limit=self.batch_rows,
            )
            if not batch:
                break
            self.datasets.write_stream(
                ARCHIVE_DATASET,
                (_archive_row(event) for event in batch),
                namespace=self.namespace,
            )
            self.events.remove_through(batch[-1].seq)
            report.through = batch[-1].seq
            report.archived += len(batch)
            report.batches += 1
        return report

    def _ensure_dataset(self) -> None:
        try:
            self.datasets.describe(ARCHIVE_DATASET, namespace=self.namespace)
        except DatasetNotFoundError:
            try:
                self.datasets.create(archive_spec(self.namespace))
            except DatasetAlreadyExistsError:
                pass  # another engine created it meanwhile

    def _archived_through(self) -> int:
        rows = self.datasets.query(
            f"SELECT COALESCE(max(seq), 0) AS through FROM {ARCHIVE_DATASET}",
            namespace=self.namespace,
        ).rows
        return int(rows[0]["through"]) if rows else 0
