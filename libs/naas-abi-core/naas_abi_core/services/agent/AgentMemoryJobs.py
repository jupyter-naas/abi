"""Engine agent memory as kernel jobs: copy it into the Document Service, prune it.

Not a module: ``Engine.job_owners`` hosts these jobs under
``AGENT_MEMORY_JOBS_OWNER`` in NATS mode, when the Document Service backs the
agent checkpointer (docs/adr/20261002_engine-agent-memory-in-documents.md).
Handlers are sync and run in a worker thread.

- ``agent_memory_migrate`` has no trigger. An admin runs it from the Nexus System
  app (Jobs tab, Run now) right after the deploy that moves agents onto the
  Document Service: a dry run first, then with ``"apply": true``. Payload:
  ``{"from": "postgres" | "documents-v1", "threads": [...], "apply": false}``.
  The PostgreSQL database is the engine's ``POSTGRES_URL`` (its secrets, then
  the environment), never a payload value: payloads are stored on the run
  record and shown in the UI, and errors never repeat the URL.
- ``agent_memory_prune`` runs daily, as ``abi agent prune-memory --apply``.
  Optional payload: ``keep_last``, ``threads``, ``min_age_seconds``, ``apply``.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterable, Iterator
from contextlib import AbstractContextManager
from datetime import timedelta
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from naas_abi_core.module.jobs import Cron, JobContext, JobsMixin, job
from naas_abi_core.services.agent.CheckpointMigration import (
    MigrationSummary,
    migrate_checkpoints,
    postgres_source,
)
from naas_abi_core.services.agent.DocumentCheckpointSaver import (
    DocumentCheckpointSaver,
    LegacyDocumentCheckpointReader,
)
from naas_abi_core.services.document.DocumentPort import CollectionNotFound

AGENT_MEMORY_JOBS_OWNER = "naas_abi_core.agent_memory"
POSTGRES_URL = "POSTGRES_URL"
SOURCES = ("postgres", "documents-v1")
DEFAULT_KEEP_LAST = 20  # as `abi agent prune-memory`
DEFAULT_MIN_AGE_SECONDS = 60
# Thread ids listed in a result: the job host keeps at most 64 KiB of it.
MAX_LISTED = 200

PostgresOpener = Callable[
    [str], AbstractContextManager[tuple[BaseCheckpointSaver, list[str]]]
]


def postgres_url_from(secrets: Any | None) -> Callable[[], str | None]:
    """Reads ``POSTGRES_URL`` when a job runs: from the engine's secrets, else the
    environment (where agents outside an engine read it)."""

    def read() -> str | None:
        value = secrets.get(POSTGRES_URL) if secrets is not None else None
        return value or os.environ.get(POSTGRES_URL) or None

    return read


class AgentMemoryJobs(JobsMixin):
    _sync_jobs = True

    def __init__(
        self,
        memory: DocumentCheckpointSaver,
        *,
        postgres_url: Callable[[], str | None],
        open_postgres: PostgresOpener = postgres_source,
    ) -> None:
        """``memory``: the engine's agent checkpointer (``Engine.load`` binds it)."""
        self.memory = memory
        self.postgres_url = postgres_url
        self.open_postgres = open_postgres

    @classmethod
    def for_engine(
        cls, memory: DocumentCheckpointSaver, services: Any
    ) -> AgentMemoryJobs:
        """The owner ``Engine.job_owners`` registers: ``POSTGRES_URL`` comes from
        the engine's secret service when it has one."""
        secrets = services.secret if services.secret_available() else None
        return cls(memory, postgres_url=postgres_url_from(secrets))

    @job("agent_memory_migrate", timeout=timedelta(hours=6))
    def migrate(self, ctx: JobContext) -> dict[str, Any]:
        """Copy agent memory into the Document Service; a dry run unless "apply": true."""
        _known(
            ctx.payload,
            ("from", "threads", "apply"),
            "the PostgreSQL database is the engine's POSTGRES_URL, never a payload value",
        )
        origin = ctx.payload.get("from", "postgres")
        if origin not in SOURCES:
            raise ValueError(f'"from" must be one of {list(SOURCES)}')
        threads = _threads(ctx.payload)
        apply = _flag(ctx.payload, "apply", False)
        target = DocumentCheckpointSaver(
            self.memory.documents, agent_id=self.memory.agent_id, legacy_reads=False
        )
        if apply:
            target.setup()
        summary = self._migrate(ctx, origin, threads, target, apply)
        report = {
            "mode": "applied" if apply else "dry-run",
            "source": origin,
            "target": {
                "namespace": self.memory.documents.namespace,
                "agent_id": self.memory.agent_id,
                "schema": 2,
            },
            **summary.as_dict(),
        }
        _cut(report, "diverged")
        ctx.log(
            f"{report['mode']} from {origin}: {summary.threads} threads, "
            f"{summary.checkpoints} checkpoints; {summary.present} already stored, "
            f"{summary.missing} missing, {summary.copied} copied"
        )
        if summary.diverged:
            ctx.log(
                f"{len(summary.diverged)} threads diverged: continued on documents "
                "before this copy, their newer head hides the copied history"
            )
        return report

    def _migrate(
        self,
        ctx: JobContext,
        origin: str,
        threads: list[str],
        target: DocumentCheckpointSaver,
        apply: bool,
    ) -> MigrationSummary:
        if origin == "documents-v1":
            reader = LegacyDocumentCheckpointReader(
                self.memory.documents, agent_id=self.memory.agent_id
            )
            try:
                available = list(reader.thread_ids())
            except CollectionNotFound:  # never written in schema 1
                available = []
            return migrate_checkpoints(
                reader,
                target,
                threads=_until_cancelled(ctx, threads or available),
                apply=apply,
            )
        url = self.postgres_url()
        if not url:
            raise ValueError(
                "POSTGRES_URL is not set in the engine's secrets or environment: "
                "there is no PostgreSQL agent memory to copy"
            )
        from psycopg.errors import UndefinedTable

        try:
            with self.open_postgres(url) as (source, available):
                return migrate_checkpoints(
                    source,
                    target,
                    threads=_until_cancelled(ctx, threads or available),
                    apply=apply,
                )
        except UndefinedTable:
            ctx.log(
                "The POSTGRES_URL database has no LangGraph checkpoints table: "
                "nothing to copy"
            )
            return MigrationSummary()
        except Exception as exc:
            message = str(exc)
            redacted = _redact(message, url)
            if redacted == message:
                raise
            raise RuntimeError(f"{type(exc).__name__}: {redacted}") from None

    @job(
        "agent_memory_prune",
        triggers=(Cron("0 0 3 * * *", time_zone="UTC"),),
        timeout=timedelta(hours=3),
    )
    def prune(self, ctx: JobContext) -> dict[str, Any]:
        """Delete old agent memory, keeping each thread's newest checkpoints."""
        _known(ctx.payload, ("keep_last", "threads", "min_age_seconds", "apply"))
        keep_last = _count(ctx.payload, "keep_last", DEFAULT_KEEP_LAST, 1)
        min_age = _count(ctx.payload, "min_age_seconds", DEFAULT_MIN_AGE_SECONDS, 0)
        apply = _flag(ctx.payload, "apply", True)
        threads = _threads(ctx.payload)
        if not threads:
            try:
                threads = list(self.memory.thread_ids())
            except CollectionNotFound:  # no agent memory yet
                threads = []
        reports = [
            self.memory.prune(
                thread_id,
                keep_last=keep_last,
                apply=apply,
                grace=timedelta(seconds=min_age),
            )
            for thread_id in _until_cancelled(ctx, threads)
        ]
        totals = {
            name: sum(getattr(report, name) for report in reports)
            for name in ("kept", "checkpoints", "writes", "values")
        }
        pruned = [
            {
                "thread_id": r.thread_id,
                "kept": r.kept,
                "checkpoints": r.checkpoints,
                "writes": r.writes,
                "values": r.values,
            }
            for r in reports
            if r.checkpoints or r.writes or r.values
        ]
        report: dict[str, Any] = {
            "mode": "applied" if apply else "dry-run",
            "keep_last": keep_last,
            "threads": len(reports),
            **totals,
            "pruned": pruned,
        }
        _cut(report, "pruned")
        ctx.log(
            f"{report['mode']}: {totals['checkpoints']} checkpoints, "
            f"{totals['writes']} writes and {totals['values']} values from "
            f"{len(pruned)} of {len(reports)} threads"
        )
        return report


def _until_cancelled(ctx: JobContext, thread_ids: Iterable[str]) -> Iterator[str]:
    for thread_id in thread_ids:
        if ctx.cancelled.is_set():
            ctx.log("Cancelled: the threads not read yet are left for the next run")
            return
        yield thread_id


def _known(payload: dict[str, Any], keys: tuple[str, ...], hint: str = "") -> None:
    unknown = sorted(set(payload) - set(keys))
    if unknown:
        raise ValueError(
            f"Unknown payload keys {unknown}: expected {list(keys)}"
            + (f" ({hint})" if hint else "")
        )


def _threads(payload: dict[str, Any]) -> list[str]:
    """``threads`` (default: every thread)."""
    threads = payload.get("threads")
    if threads is None:
        return []
    if not isinstance(threads, list) or not all(
        isinstance(t, str) and t for t in threads
    ):
        raise ValueError('"threads" must be a list of thread ids')
    return threads


def _flag(payload: dict[str, Any], key: str, default: bool) -> bool:
    value = payload.get(key, default)
    if not isinstance(value, bool):  # "false" would be truthy
        raise ValueError(f'"{key}" must be true or false')  # noqa: TRY004 - payload validation
    return value


def _count(payload: dict[str, Any], key: str, default: int, minimum: int) -> int:
    value = payload.get(key, default)
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise ValueError(f'"{key}" must be an integer of at least {minimum}')
    return value


def _cut(report: dict[str, Any], key: str) -> None:
    """At most ``MAX_LISTED`` entries of ``report[key]``; the others are counted."""
    listed = report[key]
    if len(listed) > MAX_LISTED:
        report[key] = listed[:MAX_LISTED]
        report[f"{key}_omitted"] = len(listed) - MAX_LISTED


def _redact(text: str, url: str) -> str:
    """``text`` without ``url`` or the password it holds."""
    secrets = [url]
    try:
        from psycopg.conninfo import conninfo_to_dict

        password = conninfo_to_dict(url).get("password")
    except Exception:  # noqa: BLE001 - an unparsable URL has no password to find
        password = None
    if password:
        secrets.append(str(password))
    for secret in sorted(secrets, key=len, reverse=True):
        text = text.replace(secret, "***")
    return text
