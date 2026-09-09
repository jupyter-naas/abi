import base64
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from naas_abi_core.services.document.adapters.secondary.document_codec import (
    sqlite_equal,
    sqlite_json_key,
)
from naas_abi_core.services.document.adapters.secondary.document_sql import DocumentSQL
from naas_abi_core.services.document.DocumentPort import UniqueViolation


class DocumentSecondaryAdapterSQLite(DocumentSQL):
    """SQLite JSON store. One connection per adapter, serialized across threads."""

    def __init__(self, path: str = "storage/documents.sqlite", timeout: float = 5.0):
        super().__init__(
            postgres=False,
            documents="abi_documents",
            collections="abi_document_collections",
        )
        if not path or timeout <= 0:
            raise ValueError("path must be nonempty and timeout must be positive")
        if sqlite3.sqlite_version_info < (3, 38, 0):
            raise RuntimeError(
                "Document storage requires SQLite >= 3.38 with JSON support"
            )
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._connection = sqlite3.connect(
            path, timeout=timeout, check_same_thread=False, isolation_level=None
        )
        self._connection.create_function(
            "document_equal", 2, sqlite_equal, deterministic=True
        )
        self._connection.create_function(
            "document_json_key", 1, sqlite_json_key, deterministic=True
        )
        self._connection.create_function(
            "document_bytes_key",
            1,
            lambda value: base64.b64decode(value).hex() if value else "",
            deterministic=True,
        )
        try:
            self._connection.execute("PRAGMA journal_mode=WAL")
            with self.transaction(write=True) as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS abi_document_collections (namespace TEXT NOT NULL, name TEXT NOT NULL, spec TEXT NOT NULL, PRIMARY KEY (namespace, name))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS abi_documents (namespace TEXT NOT NULL, collection TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY (namespace, collection, id))"
                )
        except BaseException:
            self.close()
            raise

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield self._connection
                self._connection.commit()
            except sqlite3.IntegrityError as exc:
                self._connection.rollback()
                if exc.sqlite_errorcode in (
                    sqlite3.SQLITE_CONSTRAINT_UNIQUE,
                    sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
                ):
                    raise UniqueViolation(
                        "Document violates a unique constraint"
                    ) from exc
                raise
            except BaseException:
                self._connection.rollback()
                raise

    def close(self) -> None:
        with self._lock:
            self._connection.close()
