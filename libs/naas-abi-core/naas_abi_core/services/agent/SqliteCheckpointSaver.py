from __future__ import annotations

import os
import pickle
import sqlite3
import threading
import time
from collections import defaultdict
from typing import Any

from langgraph.checkpoint.base import (
    ChannelVersions,
    Checkpoint,
    CheckpointMetadata,
    CheckpointTuple,
    RunnableConfig,
)
from langgraph.checkpoint.memory import InMemorySaver


class SqliteCheckpointSaver(InMemorySaver):
    """SQLite-backed checkpoint saver for local persistence.

    This saver extends LangGraph's in-memory saver and persists its internal
    structures after each write/delete operation.
    """

    def __init__(
        self,
        path: str,
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        super().__init__()
        self._lock = threading.RLock()
        self._path = path

        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(
            path,
            timeout=max(0.0, busy_timeout_ms / 1000),
            check_same_thread=False,
        )
        self._conn.execute(f"PRAGMA journal_mode={journal_mode}")
        self._conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        self._conn.execute("PRAGMA synchronous=NORMAL")
        self._conn.execute(
            """
            CREATE TABLE IF NOT EXISTS checkpoint_state (
                id INTEGER PRIMARY KEY CHECK(id = 1),
                storage BLOB NOT NULL,
                writes BLOB NOT NULL,
                blobs BLOB NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        self._conn.commit()
        self._load_state()

    def _serialize_storage(self) -> dict[str, dict[str, dict[str, tuple[Any, ...]]]]:
        return {
            thread_id: {
                checkpoint_ns: dict(checkpoints)
                for checkpoint_ns, checkpoints in namespaces.items()
            }
            for thread_id, namespaces in self.storage.items()
        }

    def _load_state(self) -> None:
        row = self._conn.execute(
            "SELECT storage, writes, blobs FROM checkpoint_state WHERE id = 1"
        ).fetchone()
        if row is None:
            return

        raw_storage = pickle.loads(row[0])
        raw_writes = pickle.loads(row[1])
        raw_blobs = pickle.loads(row[2])

        storage: defaultdict[
            str,
            dict[
                str, dict[str, tuple[tuple[str, bytes], tuple[str, bytes], str | None]]
            ],
        ] = defaultdict(lambda: defaultdict(dict))
        for thread_id, namespaces in raw_storage.items():
            for checkpoint_ns, checkpoints in namespaces.items():
                storage[thread_id][checkpoint_ns].update(checkpoints)

        writes: defaultdict[
            tuple[str, str, str],
            dict[tuple[str, int], tuple[str, str, tuple[str, bytes], str]],
        ] = defaultdict(dict)
        for key, value in raw_writes.items():
            writes[key] = value

        self.storage = storage
        self.writes = writes
        self.blobs = raw_blobs

    def _persist_state(self) -> None:
        self._conn.execute(
            """
            INSERT INTO checkpoint_state(id, storage, writes, blobs, updated_at)
            VALUES(1, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                storage=excluded.storage,
                writes=excluded.writes,
                blobs=excluded.blobs,
                updated_at=excluded.updated_at
            """,
            (
                pickle.dumps(
                    self._serialize_storage(), protocol=pickle.HIGHEST_PROTOCOL
                ),
                pickle.dumps(dict(self.writes), protocol=pickle.HIGHEST_PROTOCOL),
                pickle.dumps(dict(self.blobs), protocol=pickle.HIGHEST_PROTOCOL),
                time.time(),
            ),
        )
        self._conn.commit()

    def get_tuple(self, config: RunnableConfig) -> CheckpointTuple | None:
        with self._lock:
            return super().get_tuple(config)

    def list(
        self,
        config: RunnableConfig | None,
        *,
        filter: dict[str, Any] | None = None,
        before: RunnableConfig | None = None,
        limit: int | None = None,
    ):
        with self._lock:
            yield from super().list(config, filter=filter, before=before, limit=limit)

    def put(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: ChannelVersions,
    ) -> RunnableConfig:
        with self._lock:
            updated_config = super().put(config, checkpoint, metadata, new_versions)
            self._persist_state()
            return updated_config

    def put_writes(
        self,
        config: RunnableConfig,
        writes,
        task_id: str,
        task_path: str = "",
    ) -> None:
        with self._lock:
            super().put_writes(config, writes, task_id, task_path)
            self._persist_state()

    def delete_thread(self, thread_id: str) -> None:
        with self._lock:
            super().delete_thread(thread_id)
            self._persist_state()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
