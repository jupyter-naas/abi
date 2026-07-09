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

from .desktop_config import DEFAULT_SETTINGS

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
    created_at REAL NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_chat ON messages(chat_id, created_at);
"""


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


def _row_to_message(row: sqlite3.Row) -> dict[str, Any]:
    try:
        parts = json.loads(row["parts_json"])
    except Exception:
        parts = []
    return {
        "id": row["id"],
        "chat_id": row["chat_id"],
        "role": row["role"],
        "content": row["content"],
        "parts": parts,
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
            self._conn.commit()

    # -- messages -----------------------------------------------------------

    def add_message(
        self,
        chat_id: str,
        role: str,
        content: str,
        parts: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        now = time.time()
        message_id = uuid.uuid4().hex
        with self._lock:
            self._conn.execute(
                "INSERT INTO messages(id, chat_id, role, content, parts_json, created_at) "
                "VALUES(?, ?, ?, ?, ?, ?)",
                (message_id, chat_id, role, content, json.dumps(parts or []), now),
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
            "created_at": now,
        }

    def list_messages(self, chat_id: str) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM messages WHERE chat_id=? ORDER BY created_at",
                (chat_id,),
            ).fetchall()
        return [_row_to_message(row) for row in rows]
