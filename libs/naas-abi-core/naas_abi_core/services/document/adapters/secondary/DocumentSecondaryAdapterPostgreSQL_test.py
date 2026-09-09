import os
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
    @pytest.fixture
    def connection_options(self):
        dsn = os.environ.get("DOCUMENT_TEST_POSTGRES_DSN")
        if not dsn:
            pytest.skip("Set DOCUMENT_TEST_POSTGRES_DSN to run the PostgreSQL contract")
        return {"dsn": dsn, "schema": "document_test_" + uuid4().hex}

    @pytest.fixture
    def peer(self, connection_options, adapter):
        return DocumentSecondaryAdapterPostgreSQL(**connection_options)

    @pytest.fixture
    def adapter(self, connection_options):
        import psycopg
        from psycopg import sql

        adapter = DocumentSecondaryAdapterPostgreSQL(**connection_options)
        try:
            yield adapter
        finally:
            with psycopg.connect(connection_options["dsn"]) as connection:
                connection.execute(
                    sql.SQL("DROP SCHEMA {} CASCADE").format(
                        sql.Identifier(connection_options["schema"])
                    )
                )
