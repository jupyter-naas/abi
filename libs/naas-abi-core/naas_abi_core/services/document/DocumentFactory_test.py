from unittest.mock import patch

from naas_abi_core.services.document.DocumentFactory import DocumentFactory
from naas_abi_core.services.document.DocumentPort import CollectionSpec


def test_sqlite_factory_creates_usable_namespaced_service(tmp_path):
    documents = DocumentFactory.DocumentServiceSQLite(
        str(tmp_path / "factory.sqlite"), "module"
    )
    documents.ensure_collection(CollectionSpec(name="records"))
    documents.put("records", "id", {"value": True})
    assert documents.namespace == "module"
    assert documents.get("records", "id").data == {"value": True}


def test_postgresql_factory_forwards_connection_options():
    with patch(
        "naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterPostgreSQL.DocumentSecondaryAdapterPostgreSQL"
    ) as adapter:
        documents = DocumentFactory.DocumentServicePostgreSQL(
            "dbname=test",
            "module",
            schema="documents",
            connect_timeout=2,
            statement_timeout=4000,
            pool_max_size=10,
            pool_timeout=5.0,
        )
        assert documents.namespace == "module"
        adapter.assert_called_once_with(
            "dbname=test",
            schema="documents",
            connect_timeout=2,
            statement_timeout=4000,
            pool_max_size=10,
            pool_timeout=5.0,
        )
