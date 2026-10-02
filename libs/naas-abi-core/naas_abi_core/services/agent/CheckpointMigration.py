"""Copy LangGraph threads from a checkpoint saver into the document service.

Moves agent memory out of LangGraph's PostgreSQL tables (PostgresSaver), or out
of document schema 1 (``LegacyDocumentCheckpointReader``), into schema 2
(``DocumentCheckpointSaver``). The source is read through LangGraph's public
saver API and the target written through its ``put``/``put_writes``.

One-shot and idempotent. Without a target it is a dry run that only reads the
source. With one, each checkpoint the target lacks is written oldest first, so
an interrupted run leaves complete older history, and the target stores only
what changed between steps. Pending writes are sent again (the first write of a
task wins: repeats change nothing). Run it while no agent writes to the source.
A thread whose schema 2 history does not grow out of the source's (an engine
served it on documents before the copy) is reported as ``diverged``: its newer
head hides the copied history.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any

from langgraph.checkpoint.base import (
    WRITES_IDX_MAP,
    BaseCheckpointSaver,
    CheckpointTuple,
)

if TYPE_CHECKING:
    from naas_abi_core.services.agent.DocumentCheckpointSaver import (
        DocumentCheckpointSaver,
    )


@dataclass
class MigrationSummary:
    threads: int = 0
    checkpoints: int = 0
    writes: int = 0
    # Applied runs only: checkpoints written, and those the target already had.
    copied: int = 0
    present: int = 0
    # Threads whose schema 2 history does not continue the source's.
    diverged: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


def postgres_thread_ids(connection: Any) -> list[str]:
    """Thread IDs in LangGraph's PostgreSQL ``checkpoints`` table.

    LangGraph has no public thread listing, and ``PostgresSaver.list(None)``
    fetches every checkpoint at once; this reads only the IDs.
    """
    with connection.cursor() as cursor:
        cursor.execute("SELECT DISTINCT thread_id FROM checkpoints ORDER BY thread_id")
        return [
            row["thread_id"] if isinstance(row, dict) else row[0]
            for row in cursor.fetchall()
        ]


def migrate_checkpoints(
    source: BaseCheckpointSaver,
    target: DocumentCheckpointSaver | None = None,
    *,
    threads: Iterable[str] | None = None,
) -> MigrationSummary:
    """Copy ``threads`` (default: every thread ``source.list(None)`` finds)."""
    if threads is None:
        threads = sorted(
            {item.config["configurable"]["thread_id"] for item in source.list(None)}
        )
    summary = MigrationSummary()
    for thread_id in threads:
        # Every checkpoint namespace of the thread (subgraphs included), newest first.
        history = list(source.list({"configurable": {"thread_id": thread_id}}))
        if not history:
            continue
        summary.threads += 1
        summary.checkpoints += len(history)
        summary.writes += sum(len(item.pending_writes or ()) for item in history)
        if target is not None:
            _copy_thread(target, thread_id, history, summary)
    return summary


def _copy_thread(
    target: DocumentCheckpointSaver,
    thread_id: str,
    history: list[CheckpointTuple],
    summary: MigrationSummary,
) -> None:
    source_ids = {item.config["configurable"]["checkpoint_id"] for item in history}
    lineage = target.lineage(thread_id)
    if lineage is not None and not source_ids & set(lineage):
        summary.diverged.append(thread_id)
    for item in reversed(history):
        if not target.contains(item.config):
            configurable = item.config["configurable"]
            parent = {
                "thread_id": thread_id,
                "checkpoint_ns": configurable["checkpoint_ns"],
            }
            if item.parent_config is not None:
                parent["checkpoint_id"] = item.parent_config["configurable"][
                    "checkpoint_id"
                ]
            target.put(
                {"configurable": parent},
                item.checkpoint,
                item.metadata,
                item.checkpoint["channel_versions"],
            )
            summary.copied += 1
        else:
            summary.present += 1
        for task_id, writes in _writes_by_task(item).items():
            # Ordinary and special writes apart, so ordinary ones keep their indices.
            for group in (
                [w for w in writes if w[0] not in WRITES_IDX_MAP],
                [w for w in writes if w[0] in WRITES_IDX_MAP],
            ):
                if group:
                    target.put_writes(item.config, group, task_id)


def _writes_by_task(item: CheckpointTuple) -> dict[str, list[tuple[str, Any]]]:
    grouped: dict[str, list[tuple[str, Any]]] = {}
    for task_id, channel, value in item.pending_writes or ():
        grouped.setdefault(task_id, []).append((channel, value))
    return grouped
