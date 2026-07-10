"""SQLite persistence for ABI Desktop (chats, messages, settings).

Uses the stdlib ``sqlite3`` module (no ORM) so the compiled executable
stays small. All access goes through :class:`DesktopStore`, one connection
per instance with ``check_same_thread=False`` guarded by a lock — traffic
is a single local user, so contention is negligible.
"""

from __future__ import annotations

import json
import sqlite3
import time
import uuid
from pathlib import Path
from threading import Lock
from typing import Any

from ..config.desktop_config import DEFAULT_SETTINGS

_SCHEMA = """
CREATE TABLE IF NOT EXISTS settings (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chats (
    id                  TEXT PRIMARY KEY,
    title               TEXT NOT NULL,
    section             TEXT NOT NULL DEFAULT 'chat',
    opencode_session_id TEXT,
    model               TEXT,
    created_at          REAL NOT NULL,
    updated_at          REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id         TEXT PRIMARY KEY,
    chat_id    TEXT NOT NULL REFERENCES chats(id) ON DELETE CASCADE,
    role       TEXT NOT NULL,
    content    TEXT NOT NULL DEFAULT '',
    parts_json TEXT NOT NULL DEFAULT '[]',
    sources_json TEXT NOT NULL DEFAULT '[]',
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);

CREATE TABLE IF NOT EXISTS aspect_entities (
    id          TEXT PRIMARY KEY,
    bucket      TEXT NOT NULL,
    entity_iri  TEXT,
    label       TEXT NOT NULL,
    value_key   TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(bucket, value_key)
);

CREATE TABLE IF NOT EXISTS processes (
    id              TEXT PRIMARY KEY,
    process_type    TEXT NOT NULL,
    process_label   TEXT NOT NULL,
    source_ref      TEXT,
    workspace_org   TEXT,
    workspace_model TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);

CREATE TABLE IF NOT EXISTS process_aspects (
    process_id   TEXT NOT NULL REFERENCES processes(id) ON DELETE CASCADE,
    bucket       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'known',
    entity_id    TEXT REFERENCES aspect_entities(id),
    aspect_label TEXT,
    aspect_iri   TEXT,
    bfo_property TEXT,
    detail_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (process_id, bucket)
);

CREATE INDEX IF NOT EXISTS idx_processes_type ON processes(process_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_process_aspects_entity ON process_aspects(entity_id);
"""

# Seven BFO bucket slots persisted per process (Option B star schema).
PROCESS_BUCKETS: tuple[str, ...] = (
    "process",
    "temporal",
    "material",
    "site",
    "quality",
    "information",
    "role",
)

_BUCKET_BFO_PROPERTIES: dict[str, str] = {
    "temporal": "occupiesTemporalRegion",
    "material": "hasParticipant",
    "site": "occursIn",
    "quality": "inheresIn",
    "information": "concretizes",
    "role": "realizes",
}

_BUCKET_ENTITY_IRIS: dict[str, str] = {
    "process": "http://ontology.naas.ai/abi/desktop#ChatProcess",
    "temporal": "http://ontology.naas.ai/abi/desktop#ChatTemporalRegion",
    "material": "http://ontology.naas.ai/abi/desktop#UserParticipant",
    "site": "http://ontology.naas.ai/abi/desktop#HarnessSite",
    "quality": "http://ontology.naas.ai/abi/desktop#SectionQuality",
    "information": "http://ontology.naas.ai/abi/desktop#ChatStorageRecord",
    "role": "http://ontology.naas.ai/abi/desktop#HarnessAgentRole",
}


def _row_to_chat(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "section": row["section"],
        "opencode_session_id": row["opencode_session_id"],
        "model": row["model"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


def _format_process_timestamp(value: Any) -> str:
    try:
        from datetime import UTC, datetime

        ts = float(value)
        return datetime.fromtimestamp(ts, tz=UTC).strftime("%Y-%m-%d %H:%M")
    except (TypeError, ValueError):
        return str(value) if value else "unknown"


def process_graph_node_id(
    process_type: str, process_id: str, *, source_ref: str | None = None
) -> str:
    if process_type == "chat":
        return f"chat:{process_id}:process"
    if process_type == "route" and source_ref:
        return f"route:{source_ref}:process"
    return f"{process_type}:{process_id}:process"


def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    try:
        parts = json.loads(row["parts_json"])
    except Exception:
        parts = []
    try:
        sources = json.loads(row["sources_json"])
    except Exception:
        sources = []
    if not isinstance(sources, list):
        sources = []
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "role": row["role"],
        "content": row["content"],
        "parts": parts,
        "sources": sources,
        "created_at": row["created_at"],
    }


class DesktopStore:
    def __init__(self, db_path: Path):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.executescript(_SCHEMA)
        self._migrate_schema()
        self._conn.commit()

    def _migrate_schema(self) -> None:
        columns = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(messages)").fetchall()
        }
        if "sources_json" not in columns:
            self._conn.execute(
                "ALTER TABLE messages ADD COLUMN sources_json TEXT NOT NULL DEFAULT '[]'"
            )
        process_tables = {
            row[0]
            for row in self._conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        if "processes" not in process_tables:
            self._conn.executescript(
                """
CREATE TABLE IF NOT EXISTS aspect_entities (
    id          TEXT PRIMARY KEY,
    bucket      TEXT NOT NULL,
    entity_iri  TEXT,
    label       TEXT NOT NULL,
    value_key   TEXT NOT NULL,
    detail_json TEXT NOT NULL DEFAULT '{}',
    UNIQUE(bucket, value_key)
);
CREATE TABLE IF NOT EXISTS processes (
    id              TEXT PRIMARY KEY,
    process_type    TEXT NOT NULL,
    process_label   TEXT NOT NULL,
    source_ref      TEXT,
    workspace_org   TEXT,
    workspace_model TEXT,
    created_at      REAL NOT NULL,
    updated_at      REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS process_aspects (
    process_id   TEXT NOT NULL REFERENCES processes(id) ON DELETE CASCADE,
    bucket       TEXT NOT NULL,
    status       TEXT NOT NULL DEFAULT 'known',
    entity_id    TEXT REFERENCES aspect_entities(id),
    aspect_label TEXT,
    aspect_iri   TEXT,
    bfo_property TEXT,
    detail_json  TEXT NOT NULL DEFAULT '{}',
    PRIMARY KEY (process_id, bucket)
);
CREATE INDEX IF NOT EXISTS idx_processes_type ON processes(process_type, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_process_aspects_entity ON process_aspects(entity_id);
"""
            )
            self._backfill_chat_processes()

    @staticmethod
    def _normalize_value_key(value: str) -> str:
        cleaned = " ".join(str(value or "").strip().lower().split())
        return cleaned or "unknown"

    def _upsert_aspect_entity(
        self,
        bucket: str,
        label: str,
        value_key: str,
        *,
        entity_iri: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        norm = self._normalize_value_key(value_key)
        entity_id = f"entity:{bucket}:{norm.replace('/', '_').replace(' ', '_')}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO aspect_entities(id, bucket, entity_iri, label, value_key, detail_json) "
                "VALUES(?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(bucket, value_key) DO UPDATE SET "
                "label=excluded.label, entity_iri=COALESCE(excluded.entity_iri, entity_iri), "
                "detail_json=excluded.detail_json",
                (
                    entity_id,
                    bucket,
                    entity_iri,
                    label,
                    norm,
                    json.dumps(detail or {}),
                ),
            )
        return entity_id

    def _upsert_aspect_entity_unlocked(
        self,
        bucket: str,
        label: str,
        value_key: str,
        *,
        entity_iri: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> str:
        norm = self._normalize_value_key(value_key)
        entity_id = f"entity:{bucket}:{norm.replace('/', '_').replace(' ', '_')}"
        self._conn.execute(
            "INSERT INTO aspect_entities(id, bucket, entity_iri, label, value_key, detail_json) "
            "VALUES(?, ?, ?, ?, ?, ?) "
            "ON CONFLICT(bucket, value_key) DO UPDATE SET "
            "label=excluded.label, entity_iri=COALESCE(excluded.entity_iri, entity_iri), "
            "detail_json=excluded.detail_json",
            (
                entity_id,
                bucket,
                entity_iri,
                label,
                norm,
                json.dumps(detail or {}),
            ),
        )
        return entity_id

    def _backfill_chat_processes(self) -> None:
        with self._lock:
            chats = self._conn.execute("SELECT * FROM chats ORDER BY updated_at DESC").fetchall()
        for row in chats:
            self.sync_chat_process(_row_to_chat(row))

    def sync_chat_process(
        self,
        chat: dict[str, Any],
        *,
        org: str | None = None,
        model_ctx: str | None = None,
        site_label: str | None = None,
        site_iri: str | None = None,
        agent: str | None = None,
        graph_chat_id: str | None = None,
        user_message_count: int | None = None,
    ) -> dict[str, Any]:
        """Upsert a chat process row and all seven BFO bucket aspects."""
        now = time.time()
        chat_id = chat["id"]
        process_id = chat_id
        title = str(chat.get("title") or "Chat")[:80]
        section = str(chat.get("section") or "chat")
        created = chat.get("created_at") or chat.get("updated_at")
        temporal_label = _format_process_timestamp(created)
        temporal_key = str(created) if created else ""
        model_ref = str(chat.get("model") or "").strip()
        role_label = (agent or "").strip() or None

        aspect_specs: list[tuple[str, str, str, str, str | None, dict[str, Any]]] = [
            (
                "process",
                "known",
                title,
                title,
                _BUCKET_ENTITY_IRIS["process"],
                {"section": section, "chat_id": chat_id},
            ),
            (
                "temporal",
                "known" if temporal_key else "unknown",
                temporal_label if temporal_key else "Temporal: unknown",
                temporal_key or "unknown",
                _BUCKET_ENTITY_IRIS["temporal"],
                {"timestamp": created},
            ),
            (
                "material",
                "known",
                "user",
                "user",
                _BUCKET_ENTITY_IRIS["material"],
                {
                    "role": "user",
                    "message_count": user_message_count,
                    "model_ref": model_ref or None,
                },
            ),
            (
                "site",
                "known" if site_label else "unknown",
                site_label or "Site: unknown",
                site_label or "unknown",
                _BUCKET_ENTITY_IRIS["site"],
                {"site_iri": site_iri or ""},
            ),
            (
                "quality",
                "known",
                section,
                section,
                _BUCKET_ENTITY_IRIS["quality"],
                {"section": section},
            ),
            (
                "information",
                "known",
                "chats row",
                f"chat:{chat_id}",
                _BUCKET_ENTITY_IRIS["information"],
                {
                    "table": "chats",
                    "synced_to": graph_chat_id or "",
                    "chat_id": chat_id,
                },
            ),
            (
                "role",
                "known" if role_label else "unknown",
                role_label or "Role: unknown",
                role_label or "unknown",
                _BUCKET_ENTITY_IRIS["role"],
                {"agent": role_label or "", "section": section},
            ),
        ]

        with self._lock:
            self._conn.execute(
                "INSERT INTO processes("
                "id, process_type, process_label, source_ref, workspace_org, "
                "workspace_model, created_at, updated_at"
                ") VALUES(?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET "
                "process_label=excluded.process_label, "
                "workspace_org=COALESCE(excluded.workspace_org, workspace_org), "
                "workspace_model=COALESCE(excluded.workspace_model, workspace_model), "
                "updated_at=excluded.updated_at",
                (
                    process_id,
                    "chat",
                    title,
                    chat_id,
                    org,
                    model_ctx,
                    float(chat.get("created_at") or now),
                    float(chat.get("updated_at") or now),
                ),
            )
            for (
                bucket,
                status,
                label,
                value_key,
                aspect_iri,
                detail,
            ) in aspect_specs:
                entity_id: str | None = None
                entity_status = status
                if status == "known" and bucket != "process":
                    entity_id = self._upsert_aspect_entity_unlocked(
                        bucket,
                        label,
                        value_key,
                        entity_iri=aspect_iri,
                        detail=detail,
                    )
                    row = self._conn.execute(
                        "SELECT COUNT(DISTINCT process_id) AS cnt FROM process_aspects "
                        "WHERE entity_id=? AND process_id!=?",
                        (entity_id, process_id),
                    ).fetchone()
                    if row and int(row["cnt"]) > 0:
                        entity_status = "shared"
                self._conn.execute(
                    "INSERT INTO process_aspects("
                    "process_id, bucket, status, entity_id, aspect_label, "
                    "aspect_iri, bfo_property, detail_json"
                    ") VALUES(?, ?, ?, ?, ?, ?, ?, ?) "
                    "ON CONFLICT(process_id, bucket) DO UPDATE SET "
                    "status=excluded.status, entity_id=excluded.entity_id, "
                    "aspect_label=excluded.aspect_label, aspect_iri=excluded.aspect_iri, "
                    "bfo_property=excluded.bfo_property, detail_json=excluded.detail_json",
                    (
                        process_id,
                        bucket,
                        entity_status,
                        entity_id,
                        label,
                        aspect_iri,
                        _BUCKET_BFO_PROPERTIES.get(bucket, ""),
                        json.dumps(detail),
                    ),
                )
            self._conn.execute(
                "UPDATE process_aspects SET status='shared' "
                "WHERE entity_id IS NOT NULL AND entity_id IN ("
                "  SELECT entity_id FROM process_aspects "
                "  GROUP BY entity_id HAVING COUNT(DISTINCT process_id) > 1"
                ")"
            )
            self._conn.commit()
        return self.get_process_record(process_id) or {"id": process_id}

    def get_process_record(self, process_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM processes WHERE id=?", (process_id,)
            ).fetchone()
            if row is None:
                return None
            aspect_rows = self._conn.execute(
                "SELECT pa.*, ae.value_key, ae.label AS entity_label "
                "FROM process_aspects pa "
                "LEFT JOIN aspect_entities ae ON ae.id = pa.entity_id "
                "WHERE pa.process_id=? ORDER BY pa.bucket",
                (process_id,),
            ).fetchall()
        aspects: dict[str, dict[str, Any]] = {}
        for aspect_row in aspect_rows:
            try:
                detail = json.loads(aspect_row["detail_json"])
            except Exception:
                detail = {}
            aspects[aspect_row["bucket"]] = {
                "bucket": aspect_row["bucket"],
                "status": aspect_row["status"],
                "entity_id": aspect_row["entity_id"],
                "aspect_label": aspect_row["aspect_label"],
                "aspect_iri": aspect_row["aspect_iri"],
                "bfo_property": aspect_row["bfo_property"],
                "value_key": aspect_row["value_key"] or "",
                "entity_label": aspect_row["entity_label"] or "",
                "detail": detail,
            }
        return {
            "id": row["id"],
            "process_type": row["process_type"],
            "process_label": row["process_label"],
            "source_ref": row["source_ref"],
            "workspace_org": row["workspace_org"],
            "workspace_model": row["workspace_model"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "aspects": aspects,
        }

    def list_process_records(
        self, *, process_type: str | None = None, limit: int = 20
    ) -> list[dict[str, Any]]:
        events, _total = self.list_process_events(
            process_type=process_type, limit=limit, offset=0
        )
        return events

    def count_processes(self, *, process_type: str | None = None) -> int:
        query = "SELECT COUNT(*) AS cnt FROM processes"
        params: tuple[Any, ...] = ()
        if process_type:
            query += " WHERE process_type=?"
            params = (process_type,)
        with self._lock:
            row = self._conn.execute(query, params).fetchone()
        return int(row["cnt"]) if row else 0

    def list_process_events(
        self,
        *,
        process_type: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[dict[str, Any]], int]:
        """Return paginated process rows with all seven BFO bucket columns."""
        total = self.count_processes(process_type=process_type)
        query = "SELECT id FROM processes"
        params: tuple[Any, ...] = ()
        if process_type:
            query += " WHERE process_type=?"
            params = (process_type,)
        query += " ORDER BY updated_at DESC LIMIT ? OFFSET ?"
        params = (*params, max(1, limit), max(0, offset))
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        events: list[dict[str, Any]] = []
        for row in rows:
            record = self.get_process_record(row["id"])
            if record is None:
                continue
            aspects = record.get("aspects") or {}
            buckets: dict[str, dict[str, Any]] = {}
            for bucket in PROCESS_BUCKETS:
                aspect = aspects.get(bucket)
                if aspect is None:
                    buckets[bucket] = {
                        "status": "unknown",
                        "label": "",
                        "entity_id": None,
                        "value_key": "",
                    }
                else:
                    buckets[bucket] = {
                        "status": aspect.get("status") or "unknown",
                        "label": aspect.get("aspect_label") or "",
                        "entity_id": aspect.get("entity_id"),
                        "value_key": aspect.get("value_key") or "",
                    }
            events.append(
                {
                    "id": record["id"],
                    "process_type": record["process_type"],
                    "process_label": record["process_label"],
                    "source_ref": record.get("source_ref"),
                    "workspace_org": record.get("workspace_org"),
                    "workspace_model": record.get("workspace_model"),
                    "created_at": record["created_at"],
                    "updated_at": record["updated_at"],
                    "timestamp": _format_process_timestamp(record["updated_at"]),
                    "graph_node_id": process_graph_node_id(
                        record["process_type"],
                        record["id"],
                        source_ref=record.get("source_ref"),
                    ),
                    "buckets": buckets,
                }
            )
        return events, total

    def delete_process(self, process_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM processes WHERE id=?", (process_id,))
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()

    # -- settings -----------------------------------------------------------

    def get_settings(self) -> dict[str, str]:
        with self._lock:
            rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        settings = dict(DEFAULT_SETTINGS)
        settings.update({row["key"]: row["value"] for row in rows})
        return settings

    def update_settings(self, values: dict[str, str]) -> dict[str, str]:
        with self._lock:
            self._conn.executemany(
                "INSERT INTO settings(key, value) VALUES(?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                [(k, str(v)) for k, v in values.items()],
            )
            self._conn.commit()
        return self.get_settings()

    # -- chats --------------------------------------------------------------

    def create_chat(
        self,
        title: str = "New chat",
        section: str = "chat",
        model: str | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        chat_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO chats(id, title, section, model, created_at, updated_at) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (chat_id, title, section, model, now, now),
            )
            self._conn.commit()
        chat = self.get_chat(chat_id)
        assert chat is not None
        self.sync_chat_process(chat)
        return chat

    def get_chat(self, chat_id: str) -> dict[str, Any] | None:
        with self._lock:
            row = self._conn.execute(
                "SELECT * FROM chats WHERE id=?", (chat_id,)
            ).fetchone()
        return _row_to_chat(row) if row else None

    def list_chats(self, section: str | None = None) -> list[dict[str, Any]]:
        query = "SELECT * FROM chats"
        params: tuple[Any, ...] = ()
        if section:
            query += " WHERE section=?"
            params = (section,)
        query += " ORDER BY updated_at DESC"
        with self._lock:
            rows = self._conn.execute(query, params).fetchall()
        return [_row_to_chat(row) for row in rows]

    def update_chat(self, chat_id: str, **fields: Any) -> dict[str, Any] | None:
        allowed = {"title", "opencode_session_id", "model"}
        updates = {k: v for k, v in fields.items() if k in allowed}
        if updates:
            updates["updated_at"] = time.time()
            assignments = ", ".join(f"{key}=?" for key in updates)
            with self._lock:
                self._conn.execute(
                    f"UPDATE chats SET {assignments} WHERE id=?",  # nosec B608
                    (*updates.values(), chat_id),
                )
                self._conn.commit()
        return self.get_chat(chat_id)

    def delete_chat(self, chat_id: str) -> None:
        with self._lock:
            self._conn.execute("DELETE FROM chats WHERE id=?", (chat_id,))
            self._conn.execute("DELETE FROM processes WHERE id=?", (chat_id,))
            self._conn.commit()

    # -- messages -----------------------------------------------------------

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        parts: list[dict[str, Any]] | None = None,
        sources: list[str] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        message_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages(id, chat_id, role, content, parts_json, sources_json, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?, ?)",
                (
                    message_id,
                    chat_id,
                    role,
                    content,
                    json.dumps(parts or []),
                    json.dumps(sources or []),
                    now,
                ),
            )
            self._conn.execute(
                "UPDATE chats SET updated_at=? WHERE id=?", (now, chat_id)
            )
            self._conn.commit()
        return {
            "id": message_id,
            "chat_id": chat_id,
            "role": role,
            "content": content,
            "parts": parts or [],
            "sources": sources or [],
            "created_at": now,
        }

    def list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at",
                (chat_id,),
            ).fetchall()
        return [_row_to_message(row) for row in rows]

    def list_recent_messages(self, limit: int = 50) -> list[dict[str, Any]]:
        """Return the most recent messages across all chats (for graph overview)."""
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [_row_to_message(row) for row in rows]
