import math
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import RLock

from naas_abi_core.services.document.adapters.secondary.document_codec import (
    encoded_bytes_sort_key,
    sqlite_field,
    sqlite_json_key,
)
from naas_abi_core.services.document.adapters.secondary.document_sql import DocumentSQL
from naas_abi_core.services.document.DocumentPort import (
    DocumentStorageError,
    UniqueViolation,
)


class DocumentSecondaryAdapterSQLite(DocumentSQL):
    """File transactions use independent connections; :memory: retains one."""

    def __init__(self, path: str = "storage/documents.sqlite", timeout: float = 5.0):
        super().__init__(
            postgres=False,
            documents="abi_documents",
            collections="abi_document_collections",
        )
        if not path or timeout <= 0 or not math.isfinite(timeout):
            raise ValueError("path must be nonempty and timeout must be positive")
        if sqlite3.sqlite_version_info < (3, 38, 0):
            raise RuntimeError(
                "Document storage requires SQLite >= 3.38 with JSON support"
            )
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()
        self._path = path
        self._timeout = timeout
        self._closed = False
        self._memory_connection: sqlite3.Connection | None = None
        try:
            if path == ":memory:":
                self._memory_connection = self._connect()
            with self._connection() as connection:
                connection.execute("PRAGMA journal_mode=WAL")
            with self.transaction(write=True) as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS abi_document_collections (namespace TEXT NOT NULL, name TEXT NOT NULL, spec TEXT NOT NULL, PRIMARY KEY (namespace, name))"
                )
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS abi_documents (namespace TEXT NOT NULL, collection TEXT NOT NULL, id TEXT NOT NULL, data TEXT NOT NULL, created_at TEXT NOT NULL, updated_at TEXT NOT NULL, version INTEGER NOT NULL, PRIMARY KEY (namespace, collection, id))"
                )
        except sqlite3.Error as exc:
            self.close()
            raise DocumentStorageError(
                "Cannot initialize SQLite document storage"
            ) from exc
        except BaseException:
            self.close()
            raise

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            self._path,
            timeout=self._timeout,
            check_same_thread=False,
            isolation_level=None,
        )
        try:
            connection.create_function(
                "document_field", 2, sqlite_field, deterministic=True
            )
            connection.create_function(
                "document_json_key", 1, sqlite_json_key, deterministic=True
            )
            connection.create_function(
                "document_bytes_key", 1, encoded_bytes_sort_key, deterministic=True
            )
            return connection
        except BaseException:
            connection.close()
            raise

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        with self._lock:
            if self._closed:
                raise DocumentStorageError("Document adapter is closed")
            if self._memory_connection is not None:
                yield self._memory_connection
                return
        connection = self._connect()
        try:
            yield connection
        finally:
            connection.close()

    def ensure_index(
        self, connection: sqlite3.Connection, name: str, statement: str
    ) -> None:
        existing = connection.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'index' AND name = ?", (name,)
        ).fetchone()
        # Repair indexes built using the old JSON-path accessor. Rebuild and
        # uniqueness validation share ensure_collection's write transaction.
        if existing is not None and existing[0] != statement.replace(
            " IF NOT EXISTS", ""
        ):
            connection.execute(f"DROP INDEX {name}")
        super().ensure_index(connection, name, statement)

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[sqlite3.Connection]:
        with self._translate_errors(), self._connection() as connection:
            connection.execute("BEGIN IMMEDIATE" if write else "BEGIN")
            try:
                yield connection
                connection.commit()
            except BaseException:
                connection.rollback()
                raise

    @contextmanager
    def _translate_errors(self) -> Iterator[None]:
        try:
            yield
        except sqlite3.IntegrityError as exc:
            if exc.sqlite_errorcode in (
                sqlite3.SQLITE_CONSTRAINT_UNIQUE,
                sqlite3.SQLITE_CONSTRAINT_PRIMARYKEY,
            ):
                raise UniqueViolation("Document violates a unique constraint") from exc
            raise DocumentStorageError(
                "SQLite document storage constraint failed"
            ) from exc
        except sqlite3.Error as exc:
            raise DocumentStorageError(
                "SQLite document storage operation failed"
            ) from exc

    def close(self) -> None:
        with self._translate_errors(), self._lock:
            self._closed = True
            if self._memory_connection is not None:
                self._memory_connection.close()
                self._memory_connection = None
