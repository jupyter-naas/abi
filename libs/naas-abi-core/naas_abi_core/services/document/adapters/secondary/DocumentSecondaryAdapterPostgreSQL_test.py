import os
from unittest.mock import patch
from uuid import uuid4

import pytest
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL import (
    DocumentSecondaryAdapterPostgreSQL,
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
        with pytest.raises(PoolClosed):
            adapter.collections("module")

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
