from __future__ import annotations

import json
import os
import sqlite3
import threading
from datetime import datetime
from typing import Any

from naas_abi_core.services.gatekeeper.GatekeeperPort import (
    IGrantStore,
    IObservationStore,
    ObservationRecord,
    ResourceGrant,
)


class GatekeeperSqliteAdapter(IObservationStore, IGrantStore):
    """Single SQLite database for observations and session grants."""

    def __init__(
        self,
        db_path: str,
        synchronous: str = "NORMAL",
        journal_mode: str = "WAL",
        busy_timeout_ms: int = 5000,
    ) -> None:
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._db_path = db_path
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute(f"PRAGMA journal_mode={journal_mode}")
        self._conn.execute(f"PRAGMA synchronous={synchronous}")
        self._conn.execute(f"PRAGMA busy_timeout={busy_timeout_ms}")
        self._init_schema()

    def _init_schema(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS observations (
                    id TEXT PRIMARY KEY,
                    chat_id TEXT NOT NULL,
                    user_id TEXT,
                    workspace_id TEXT,
                    tool_name TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    sensitivity TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    tool_args_json TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_observations_chat_id
                    ON observations(chat_id);

                CREATE TABLE IF NOT EXISTS grants (
                    chat_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    resource_id TEXT NOT NULL,
                    actions_json TEXT NOT NULL,
                    granted_at TEXT NOT NULL,
                    PRIMARY KEY (chat_id, resource_type, resource_id)
                );
                """
            )
            self._conn.commit()

    def record(self, observation: ObservationRecord) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO observations (
                    id, chat_id, user_id, workspace_id, tool_name,
                    resource_type, resource_id, sensitivity, observed_at, tool_args_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    observation.id,
                    observation.chat_id,
                    observation.user_id,
                    observation.workspace_id,
                    observation.tool_name,
                    observation.resource_type,
                    observation.resource_id,
                    observation.sensitivity,
                    observation.observed_at.isoformat(),
                    json.dumps(observation.tool_args, default=str),
                ),
            )
            self._conn.commit()

    def list_observations(self, chat_id: str) -> list[ObservationRecord]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT id, chat_id, user_id, workspace_id, tool_name,
                       resource_type, resource_id, sensitivity, observed_at, tool_args_json
                FROM observations
                WHERE chat_id = ?
                ORDER BY observed_at ASC
                """,
                (chat_id,),
            ).fetchall()
        return [self._row_to_observation(row) for row in rows]

    def grant(self, grant: ResourceGrant) -> None:
        with self._lock:
            self._conn.execute(
                """
                INSERT INTO grants (chat_id, resource_type, resource_id, actions_json, granted_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(chat_id, resource_type, resource_id) DO UPDATE SET
                    actions_json = excluded.actions_json,
                    granted_at = excluded.granted_at
                """,
                (
                    grant.chat_id,
                    grant.resource_type,
                    grant.resource_id,
                    json.dumps(sorted(grant.actions)),
                    grant.granted_at.isoformat(),
                ),
            )
            self._conn.commit()

    def list_grants(self, chat_id: str) -> list[ResourceGrant]:
        with self._lock:
            rows = self._conn.execute(
                """
                SELECT chat_id, resource_type, resource_id, actions_json, granted_at
                FROM grants
                WHERE chat_id = ?
                ORDER BY granted_at ASC
                """,
                (chat_id,),
            ).fetchall()
        return [self._row_to_grant(row) for row in rows]

    def has_grant(
        self,
        chat_id: str,
        resource_type: str,
        resource_id: str,
        action: str,
    ) -> bool:
        with self._lock:
            row = self._conn.execute(
                """
                SELECT actions_json FROM grants
                WHERE chat_id = ? AND resource_type = ? AND resource_id = ?
                """,
                (chat_id, resource_type, resource_id),
            ).fetchone()
        if row is None:
            return False
        actions = json.loads(row[0])
        return action in actions or "*" in actions

    def shutdown(self) -> None:
        with self._lock:
            self._conn.close()

    @staticmethod
    def _row_to_observation(row: tuple[Any, ...]) -> ObservationRecord:
        return ObservationRecord(
            id=row[0],
            chat_id=row[1],
            user_id=row[2],
            workspace_id=row[3],
            tool_name=row[4],
            resource_type=row[5],
            resource_id=row[6],
            sensitivity=row[7],  # type: ignore[arg-type]
            observed_at=datetime.fromisoformat(row[8]),
            tool_args=json.loads(row[9]),
        )

    @staticmethod
    def _row_to_grant(row: tuple[Any, ...]) -> ResourceGrant:
        return ResourceGrant(
            chat_id=row[0],
            resource_type=row[1],
            resource_id=row[2],
            actions=frozenset(json.loads(row[3])),
            granted_at=datetime.fromisoformat(row[4]),
        )
