import hashlib
import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL import (
    DocumentSecondaryAdapterPostgreSQL,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    DocumentStorageError,
    FieldSpec,
    UniqueViolation,
)
from naas_abi_core.services.document.tests.document__secondary_adapter__generic_test import (
    DocumentSecondaryAdapterContract,
)


@pytest.mark.integration
class TestDocumentSecondaryAdapterPostgreSQL(DocumentSecondaryAdapterContract):
    def test_pool_reuses_connections_after_rollback_and_releases_on_close(
        self, adapter
    ):
        from psycopg.pq import TransactionStatus
        from psycopg_pool import PoolClosed

        with adapter.transaction() as connection:
            pid = connection.info.backend_pid
        with (
            pytest.raises(RuntimeError, match="abort"),
            adapter.transaction() as connection,
        ):
            connection.execute("CREATE TEMP TABLE rolled_back (value INT)")
            raise RuntimeError("abort")
        with adapter.transaction() as connection:
            assert connection.info.backend_pid == pid
            assert (
                connection.execute(
                    "SELECT to_regclass('pg_temp.rolled_back')"
                ).fetchone()[0]
                is None
            )
        assert connection.info.transaction_status == TransactionStatus.IDLE
        adapter.close()
        adapter.close()
        assert connection.closed
        with pytest.raises(DocumentStorageError) as failed:
            adapter.collections("module")
        assert isinstance(failed.value.__cause__, PoolClosed)

    @pytest.mark.parametrize("duplicates", [False, True])
    def test_stale_index_is_repaired_atomically_and_unchanged_index_is_reused(
        self, docs, duplicates
    ):
        spec = CollectionSpec(
            name="records", fields=(FieldSpec(name="x", type="string", unique=True),)
        )
        docs.ensure_collection("module", spec)
        name, _ = docs.index_statements("module", spec)[0]
        qualified = docs.documents_table.rsplit(".", 1)[0] + "." + name
        with docs.transaction(write=True) as connection:
            connection.execute(f"DROP INDEX {qualified}")
            connection.execute(
                f"CREATE UNIQUE INDEX {name} ON {docs.documents_table} ((NULL::text)) WHERE namespace = 'module' AND collection = 'records'"
            )
        docs.put("module", "records", "one", {"x": "value"}, None)
        if duplicates:
            docs.put("module", "records", "two", {"x": "value"}, None)
            with pytest.raises(UniqueViolation):
                docs.ensure_collection("module", spec)
            with docs.transaction() as connection:
                definition = connection.execute(
                    "SELECT pg_get_indexdef(to_regclass(%s))", (qualified,)
                ).fetchone()[0]
                assert "NULL::text" in definition
            docs.delete("module", "records", "two", None)
        docs.ensure_collection("module", spec)
        with pytest.raises(UniqueViolation):
            docs.put("module", "records", "duplicate", {"x": "value"}, None)
        with docs.transaction() as connection:
            oid = connection.execute(
                "SELECT to_regclass(%s)::oid", (qualified,)
            ).fetchone()[0]
        docs.ensure_collection("module", spec)
        with docs.transaction() as connection:
            assert (
                connection.execute(
                    "SELECT to_regclass(%s)::oid", (qualified,)
                ).fetchone()[0]
                == oid
            )

    def test_boot_lock_wait_is_bounded_and_reported_as_storage_error(
        self, adapter, connection_options
    ):
        from psycopg.errors import QueryCanceled

        lock_id = int.from_bytes(
            hashlib.sha256(connection_options["schema"].encode()).digest()[:8],
            signed=True,
        )
        with adapter.transaction() as connection:
            connection.execute("SELECT pg_advisory_xact_lock(%s)", (lock_id,))
            with pytest.raises(DocumentStorageError) as failed:
                DocumentSecondaryAdapterPostgreSQL(
                    **connection_options, statement_timeout=100
                )
            assert isinstance(failed.value.__cause__, QueryCanceled)
        assert adapter.collections("module") == []

    def test_pool_acquisition_timeout_uses_portable_storage_error(
        self, adapter, connection_options
    ):
        from psycopg_pool import PoolTimeout

        limited = DocumentSecondaryAdapterPostgreSQL(
            **connection_options, pool_max_size=1
        )
        limited._pool.timeout = 0.05
        try:
            with limited.transaction():
                with pytest.raises(DocumentStorageError) as failed:
                    limited.collections("module")
                assert isinstance(failed.value.__cause__, PoolTimeout)
            assert limited.collections("module") == []
        finally:
            limited.close()

    @pytest.fixture
    def connection_options(self):
        dsn = os.environ.get("DOCUMENT_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip("Set DOCUMENT_TEST_POSTGRES_DSN to run the PostgreSQL contract")
        return {"dsn": dsn, "schema": "document_test_" + uuid4().hex}

    @pytest.fixture
    def peer(self, connection_options, adapter):
        peer = DocumentSecondaryAdapterPostgreSQL(**connection_options)
        yield peer
        peer.close()

    @pytest.fixture
    def adapter(self, connection_options):
        import psycopg
        from psycopg import sql

        adapter = DocumentSecondaryAdapterPostgreSQL(**connection_options)
        try:
            yield adapter
        finally:
            adapter.close()
            with psycopg.connect(connection_options["dsn"]) as connection:
                connection.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(
                        sql.Identifier(connection_options["schema"])
                    )
                )


def test_pool_is_closed_when_initialization_fails():
    with patch(
        "naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL.ConnectionPool"
    ) as pool:
        pool.return_value.open.side_effect = RuntimeError("unavailable")
        with pytest.raises(RuntimeError, match="unavailable"):
            DocumentSecondaryAdapterPostgreSQL("dbname=unused")
        pool.return_value.close.assert_called_once()
