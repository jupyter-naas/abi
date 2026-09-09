import hashlib
import re
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

import psycopg
from naas_abi_core.services.document.adapters.secondary.document_sql import DocumentSQL
from naas_abi_core.services.document.DocumentPort import UniqueViolation


class DocumentSecondaryAdapterPostgreSQL(DocumentSQL):
    """JSONB documents partitioned logically by namespace in one schema."""

    def __init__(
        self,
        dsn: str,
        schema: str = "abi_document",
        connect_timeout: int = 5,
        statement_timeout: int = 30000,
    ):
        if not re.fullmatch(r"[a-z_][a-z0-9_]{0,62}", schema):
            raise ValueError(
                "schema must be a lowercase PostgreSQL identifier (max 63 bytes)"
            )
        if not dsn or connect_timeout <= 0 or statement_timeout <= 0:
            raise ValueError("dsn must be nonempty and timeouts must be positive")
        super().__init__(
            postgres=True,
            documents=f'"{schema}".abi_documents',
            collections=f'"{schema}".abi_document_collections',
        )
        self._dsn = dsn
        self._connect_timeout = connect_timeout
        self._statement_timeout = statement_timeout
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
        try:
            with psycopg.connect(
                self._dsn, connect_timeout=self._connect_timeout
            ) as connection:
                connection.execute(
                    "SELECT set_config('statement_timeout', %s, true)",
                    (str(self._statement_timeout),),
                )
                connection.execute("SET LOCAL TIME ZONE 'UTC'")
                connection.execute("SET LOCAL standard_conforming_strings = on")
                yield connection
        except psycopg.errors.UniqueViolation as exc:
            raise UniqueViolation("Document violates a unique constraint") from exc
