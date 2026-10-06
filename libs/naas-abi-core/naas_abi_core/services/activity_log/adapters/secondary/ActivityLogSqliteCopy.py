"""Copy the per-actor SQLite activity logs into the Document Service.

The activity log's default moved from one SQLite file per actor
(``ActivityLogSqliteAdapter``, ``storage/activity_log``) to the Document Service
(docs/adr/20261006_shared-event-and-activity-log-storage.md). An installation
that needs its history runs ``activity_log_migrate`` from the Nexus System app
(Jobs tab, Run now): a dry run first, then with ``"apply": true``. Payload:
``{"data_dir": "storage/activity_log", "apply": false}``; ``data_dir`` is
relative to the engine's working directory, as in ``config.yaml``, and must be
inside its ``storage`` directory. ``ActivityLogDocumentAdapter.job_owners``
offers the job.

Each actor's events are recorded in their SQLite order through the document
adapter's ``record``, so they get new per-actor ``seq`` numbers, after any event
recorded since the switch. Idempotent: a mark per (source directory, actor), in
the ``sqlite_copies`` collection, keeps the last SQLite row handled and is saved
after each batch. Events written after the last mark (a run stopped between the
two) are recognised by their content (type, time, correlation id, attributes),
so a run copies only what is missing and never twice. Events whose values the
Document Service refuses (a non-finite number, an integer above 64 bits) are
skipped and reported; a dry run lists them too.
"""

from __future__ import annotations

import json
from collections import Counter
from collections.abc import Callable, Iterator
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from naas_abi_core.module.jobs import JobContext, JobsMixin, job
from naas_abi_core.services.activity_log.ActivityLogPort import (
    ActivityEvent,
    ActivityLogQuery,
    IActivityLogAdapter,
)
from naas_abi_core.services.activity_log.adapters.secondary.ActivityLogSqliteAdapter import (
    ActivityLogSqliteAdapter,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    DocumentNotFound,
    validate_data,
)
from naas_abi_core.services.document.DocumentService import DocumentService

ACTIVITY_LOG_JOBS_OWNER = "naas_abi_core.activity_log"
MARKS = "sqlite_copies"
DEFAULT_DATA_DIR = "storage/activity_log"  # the SQLite adapter's default
STORAGE_DIR = "storage"  # where the engine's local backends keep their files
BATCH = 500  # events read, written, then marked at a time
MAX_LISTED = 200  # actors and refused events listed in a result (64 KiB)


@dataclass
class ActorCopy:
    actor_id: str
    events: int = 0  # in the SQLite log
    present: int = 0  # in documents before this run
    missing: int = 0  # not in documents before this run
    copied: int = 0  # written by this run
    rejected: int = 0  # refused by the Document Service, this run or before


@dataclass
class CopyReport:
    mode: str
    data_dir: str
    actors: list[ActorCopy] = field(default_factory=list)
    rejected_events: list[dict[str, Any]] = field(default_factory=list)
    cancelled: bool = False

    def as_dict(self) -> dict[str, Any]:
        totals = {
            name: sum(getattr(actor, name) for actor in self.actors)
            for name in ("events", "present", "missing", "copied", "rejected")
        }
        report: dict[str, Any] = {
            "mode": self.mode,
            "data_dir": self.data_dir,
            "actors": len(self.actors),
            **totals,
            "by_actor": [asdict(actor) for actor in self.actors[:MAX_LISTED]],
            "rejected_events": self.rejected_events[:MAX_LISTED],
        }
        if len(self.actors) > MAX_LISTED:
            report["by_actor_omitted"] = len(self.actors) - MAX_LISTED
        if len(self.rejected_events) > MAX_LISTED:
            report["rejected_events_omitted"] = len(self.rejected_events) - MAX_LISTED
        return report


class ActivityLogCopyJobs(JobsMixin):
    _sync_jobs = True

    def __init__(
        self,
        target: IActivityLogAdapter,
        marks: DocumentService,
        *,
        storage_root: Path | None = None,
    ) -> None:
        """``target``: the document adapter; ``marks``: its namespace's documents.
        ``storage_root`` defaults to ``storage`` in the working directory."""
        self.target = target
        self.marks = marks
        self.storage_root = storage_root

    @job("activity_log_migrate", timeout=timedelta(hours=6))
    def migrate(self, ctx: JobContext) -> dict[str, Any]:
        """Copy the per-actor SQLite activity logs into documents; a dry run unless "apply": true."""
        unknown = sorted(set(ctx.payload) - {"data_dir", "apply"})
        if unknown:
            raise ValueError(
                f"Unknown payload keys {unknown}: expected ['data_dir', 'apply']"
            )
        apply = ctx.payload.get("apply", False)
        if not isinstance(apply, bool):  # "false" would be truthy
            raise ValueError('"apply" must be true or false')  # noqa: TRY004 - payload validation
        data_dir = ctx.payload.get("data_dir", DEFAULT_DATA_DIR)
        report = self.run(data_dir, apply=apply, cancelled=ctx.cancelled.is_set)
        if report.cancelled:
            ctx.log("Cancelled: the actors not read yet are left for the next run")
        result = report.as_dict()
        ctx.log(
            f"{report.mode} from {data_dir}: {result['actors']} actors, "
            f"{result['events']} events; {result['present']} already in documents, "
            f"{result['missing']} missing, {result['copied']} copied, "
            f"{result['rejected']} refused"
        )
        return result

    def run(
        self,
        data_dir: Any,
        *,
        apply: bool,
        cancelled: Callable[[], bool] = lambda: False,
    ) -> CopyReport:
        directory, source_key = self._resolve(data_dir)
        report = CopyReport("applied" if apply else "dry-run", data_dir)
        if apply:
            self.marks.ensure_collection(CollectionSpec(name=MARKS))
        source = ActivityLogSqliteAdapter(str(directory))
        try:
            for actor_id in sorted(source.list_actors()):
                if cancelled():
                    report.cancelled = True
                if report.cancelled:
                    break
                report.actors.append(
                    self._copy_actor(
                        source, actor_id, source_key, apply, report, cancelled
                    )
                )
        finally:
            source.shutdown()
        return report

    def _resolve(self, data_dir: Any) -> tuple[Path, str]:
        """The directory ``data_dir`` names, and its path within the storage."""
        if not isinstance(data_dir, str) or not data_dir.strip():
            raise ValueError(
                '"data_dir" must name a directory under the engine\'s storage, '
                f"such as {DEFAULT_DATA_DIR!r}"
            )
        root = (self.storage_root or Path.cwd() / STORAGE_DIR).resolve()
        directory = (Path.cwd() / data_dir).resolve()  # an absolute one stays
        if not directory.is_relative_to(root):
            raise ValueError(
                f"data_dir {data_dir!r} is outside the engine's storage directory"
            )
        if not directory.is_dir():
            raise ValueError(f"data_dir {data_dir!r} is not a directory")
        return directory, directory.relative_to(root).as_posix()

    def _copy_actor(
        self,
        source: ActivityLogSqliteAdapter,
        actor_id: str,
        source_key: str,
        apply: bool,
        report: CopyReport,
        cancelled: Callable[[], bool],
    ) -> ActorCopy:
        mark_id = json.dumps([source_key, actor_id])
        mark = self._mark(mark_id)
        after, handled, rejected = (
            int(mark["source_seq"]),
            int(mark["handled"]),
            int(mark["rejected"]),
        )
        actor = ActorCopy(
            actor_id, events=handled, present=handled - rejected, rejected=rejected
        )

        def save(source_seq: int) -> None:
            self.marks.put(
                MARKS,
                mark_id,
                {
                    "source": source_key,
                    "actor_id": actor_id,
                    "source_seq": source_seq,
                    "handled": handled,
                    "rejected": rejected,
                },
            )

        reconciling = True
        for page in _pages(source, actor_id, after):
            if cancelled():  # between batches: what is written is marked
                report.cancelled = True
                break
            actor.events += len(page)
            stored = 0
            if reconciling:  # only right after the mark can events be unmarked
                stored = self._already_copied(source, actor_id, page)
                reconciling = stored == len(page)
            actor.present += stored
            actor.missing += len(page) - stored
            if apply:
                handled += stored
            for item in page[stored:]:
                refusal = _refusal(item)
                if refusal is not None:
                    actor.rejected += 1
                    report.rejected_events.append(
                        {
                            "actor_id": actor_id,
                            "source_seq": int(item.seq or 0),
                            "error": refusal[:200],
                        }
                    )
                if not apply:
                    continue
                handled += 1
                if refusal is not None:
                    rejected += 1
                    save(int(item.seq or 0))  # unmarked events stay written ones
                    continue
                self.target.record(item)
                actor.copied += 1
            if apply:
                save(int(page[-1].seq or 0))
        return actor

    def _mark(self, mark_id: str) -> dict[str, Any]:
        try:
            return dict(self.marks.get(MARKS, mark_id).data)
        except (DocumentNotFound, CollectionNotFound):
            return {"source_seq": 0, "handled": 0, "rejected": 0}

    def _already_copied(
        self,
        source: ActivityLogSqliteAdapter,
        actor_id: str,
        events: list[ActivityEvent],
    ) -> int:
        """How many of ``events``, in order, are in documents already.

        An event counts when the documents hold at least as many events with its
        content at its timestamp as the SQLite log does up to and including it,
        so identical events are each copied once.
        """
        stored: dict[datetime, Counter[str]] = {}
        logged: dict[datetime, list[tuple[int, str]]] = {}
        for index, event in enumerate(events):
            moment = event.timestamp
            if moment not in stored:
                at = ActivityLogQuery(since=moment, until=moment)
                stored[moment] = Counter(
                    _content(e) for e in self.target.query(actor_id, at)
                )
                logged[moment] = [
                    (int(e.seq or 0), _content(e)) for e in source.query(actor_id, at)
                ]
            key = _content(event)
            needed = sum(
                1 for seq, k in logged[moment] if k == key and seq <= (event.seq or 0)
            )
            if stored[moment][key] < needed:
                return index
        return len(events)


def _pages(
    source: ActivityLogSqliteAdapter, actor_id: str, after: int
) -> Iterator[list[ActivityEvent]]:
    """The actor's SQLite events after row ``after``, ``BATCH`` at a time."""
    while True:
        page = source.query(actor_id, ActivityLogQuery(after_seq=after, limit=BATCH))
        if not page:
            return
        yield page
        if len(page) < BATCH:
            return
        after = int(page[-1].seq or 0)


def _refusal(event: ActivityEvent) -> str | None:
    """Why the Document Service refuses the values ``record`` stores, if it does."""
    try:
        validate_data(
            {
                "actor_id": event.actor_id,
                "event_type": event.event_type,
                "correlation_id": event.correlation_id,
                "attributes": event.attributes,
            }
        )
    except ValueError as exc:
        return str(exc)
    return None


def _content(event: ActivityEvent) -> str:
    return json.dumps(
        [
            event.event_type,
            event.timestamp.astimezone(UTC).isoformat(),
            event.correlation_id,
            _canonical(event.attributes),
        ],
        sort_keys=True,
    )


def _canonical(value: Any) -> Any:
    """Documents may read an integral float back as an integer."""
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, dict):
        return {key: _canonical(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_canonical(item) for item in value]
    return value
