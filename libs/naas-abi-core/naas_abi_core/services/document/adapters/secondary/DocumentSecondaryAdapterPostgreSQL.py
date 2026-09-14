import hashlib
import math
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from naas_abi_core.services.document.adapters.secondary.document_sql import DocumentSQL
from naas_abi_core.services.document.DocumentPort import (
    DocumentStorageError,
    UniqueViolation,
)
from psycopg_pool import ConnectionPool, PoolClosed, PoolTimeout


class DocumentSecondaryAdapterPostgreSQL(DocumentSQL):
    """JSONB documents partitioned logically by namespace in one schema."""

    def __init__(
        self,
        dsn: str,
        schema: str = "abi_document",
        connect_timeout: int = 5,
        statement_timeout: int = 30000,
        pool_max_size: int = 10,
        pool_timeout: float = 5.0,
    ):
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
            raise ValueError(
                "schema must be a lowercase PostgreSQL identifier (max 63 bytes)"
            )
        if (
            not dsn
            or connect_timeout <= 0
            or statement_timeout <= 0
            or pool_max_size < 1
            or pool_timeout <= 0
            or not math.isfinite(pool_timeout)
        ):
            raise ValueError("dsn must be nonempty and timeouts must be positive")
        super().__init__(
            postgres=True,
            documents=f'"{schema}".abi_documents',
            collections=f'"{schema}".abi_document_collections',
        )
        self._statement_timeout = statement_timeout
        self._pool = ConnectionPool(
            dsn,
            kwargs={"connect_timeout": connect_timeout},
            min_size=1,
            max_size=pool_max_size,
            timeout=pool_timeout,
            open=False,
        )
        try:
            self._pool.open(wait=True, timeout=pool_timeout)
            self._initialize(schema)
        except (psycopg.Error, PoolTimeout, PoolClosed) as exc:
            self._pool.close()
            raise DocumentStorageError(
                "Cannot initialize PostgreSQL document storage"
            ) from exc
        except BaseException:
            self._pool.close()
            raise

    def _initialize(self, schema: str) -> None:
        with self.transaction(write=True) as connection:
            # Serialize first-boot DDL across processes using this schema.
            lock_id = int.from_bytes(
                hashlib.sha256(schema.encode()).digest()[:8], signed=True
            )
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            connection.execute(f'CREATE SCHEMA IF NOT EXISTS "{schema}"')
            connection.execute(
                f'CREATE TABLE IF NOT EXISTS {self.collections_table} (namespace TEXT COLLATE "C" NOT NULL, name TEXT COLLATE "C" NOT NULL, spec TEXT NOT NULL, PRIMARY KEY (namespace, name))'
            )
            connection.execute(
                f'CREATE TABLE IF NOT EXISTS {self.documents_table} (namespace TEXT COLLATE "C" NOT NULL, collection TEXT COLLATE "C" NOT NULL, id TEXT COLLATE "C" NOT NULL, data JSONB NOT NULL, created_at TIMESTAMPTZ NOT NULL, updated_at TIMESTAMPTZ NOT NULL, version BIGINT NOT NULL, PRIMARY KEY (namespace, collection, id))'
            )
            connection.execute(
                f"CREATE INDEX IF NOT EXISTS abi_documents_data_gin ON {self.documents_table} USING gin (data jsonb_path_ops)"
            )

    @contextmanager
    def transaction(self, *, write: bool = False) -> Iterator[psycopg.Connection[Any]]:
        """Lease a transaction. write selects SQLite locking in the shared API.

        PostgreSQL reads also acquire catalog row locks, so they deliberately
        use read/write transactions rather than SET TRANSACTION READ ONLY.
        """
        try:
            with self._pool.connection() as connection:
                connection.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(self._statement_timeout),),
                )
                connection.execute("SET LOCAL TIME ZONE 'UTC'")
                connection.execute("SET LOCAL standard_conforming_strings = on")
                yield connection
        except psycopg.errors.UniqueViolation as exc:
            raise UniqueViolation("Document violates a unique constraint") from exc
        except (psycopg.Error, PoolTimeout, PoolClosed) as exc:
            raise DocumentStorageError(
                "PostgreSQL document storage operation failed"
            ) from exc

    def ensure_index(
        self, connection: psycopg.Connection[Any], name: str, statement: str
    ) -> None:
        qualified = self.documents_table.rsplit(".", 1)[0] + "." + name
        fingerprint = (
            "abi-document-index:" + hashlib.sha256(statement.encode()).hexdigest()
        )
        current = connection.execute(
            "SELECT obj_description(to_regclass(%s), 'pg_class')", (qualified,)
        ).fetchone()
        if current is not None and current[0] == fingerprint:
            return
        # Adapter-owned comments track the defining SQL across compiler updates.
        # Replacement and uniqueness validation share the catalog write lock.
        connection.execute(f"DROP INDEX IF EXISTS {qualified}")
        super().ensure_index(connection, name, statement)
        connection.execute(
            f"COMMENT ON INDEX {qualified} IS {self.literal(fingerprint)}", ()
        )

    def close(self) -> None:
        self._pool.close()
