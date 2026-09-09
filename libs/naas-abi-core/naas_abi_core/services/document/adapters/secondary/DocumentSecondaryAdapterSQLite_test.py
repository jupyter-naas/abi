from concurrent.futures import ThreadPoolExecutor
from threading import Event
from unittest.mock import Mock, patch

import pytest
from naas_abi_core.services.document.adapters.secondary.DocumentSecondaryAdapterSQLite import (
    DocumentSecondaryAdapterSQLite,
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


class TestDocumentSecondaryAdapterSQLite(DocumentSecondaryAdapterContract):
    def test_busy_timeout_uses_portable_storage_error_without_replaying(
        self, docs, tmp_path
    ):
        contender = DocumentSecondaryAdapterSQLite(
            str(tmp_path / "documents.sqlite"), timeout=0.05
        )
        try:
            with docs.transaction(write=True):
                with pytest.raises(DocumentStorageError) as failed:
                    contender.put("module", "records", "id", {}, None)
                assert isinstance(failed.value.__cause__, sqlite3.OperationalError)
            assert docs.count("module", "records", ()) == 0
            contender.put("module", "records", "id", {}, None)
            assert docs.count("module", "records", ()) == 1
        finally:
            contender.close()

    @pytest.mark.parametrize("duplicates", [False, True])
    def test_existing_index_is_repaired_atomically_even_when_spec_is_unchanged(
        self, docs, duplicates
    ):
        spec = CollectionSpec(
            name="records",
            fields=(FieldSpec(name='quoted"field', type="string", unique=True),),
        )
        docs.ensure_collection("module", spec)
        name, _ = docs.index_statements("module", spec)[0]
        with docs.transaction(write=True) as connection:
            connection.execute(f"DROP INDEX {name}")
            # Model an older accessor that always returned NULL for this key.
            connection.execute(
                f"CREATE UNIQUE INDEX {name} ON abi_documents (NULL) WHERE namespace = 'module' AND collection = 'records'"
            )  # nosec B608
        docs.put("module", "records", "one", {'quoted"field': "value"}, None)
        if duplicates:
            docs.put("module", "records", "two", {'quoted"field': "value"}, None)
            with pytest.raises(UniqueViolation):
                docs.ensure_collection("module", spec)
            with docs.transaction() as connection:
                sql = connection.execute(
                    "SELECT sql FROM sqlite_master WHERE name = ?", (name,)
                ).fetchone()[0]
                assert "(NULL)" in sql
            docs.delete("module", "records", "two", None)
        docs.ensure_collection("module", spec)
        with pytest.raises(UniqueViolation):
            docs.put("module", "records", "duplicate", {'quoted"field': "value"}, None)

    def test_file_readers_and_writers_use_independent_connections(self, docs):
        reading, release = Event(), Event()

        def hold_snapshot():
            with docs.transaction() as connection:
                assert (
                    connection.execute("SELECT COUNT(*) FROM abi_documents").fetchone()[
                        0
                    ]
                    == 0
                )
                reading.set()
                assert release.wait(5)
                assert (
                    connection.execute("SELECT COUNT(*) FROM abi_documents").fetchone()[
                        0
                    ]
                    == 0
                )

        with ThreadPoolExecutor(max_workers=2) as executor:
            reader = executor.submit(hold_snapshot)
            try:
                assert reading.wait(2)
                assert (
                    executor.submit(docs.count, "module", "records", ()).result(
                        timeout=2
                    )
                    == 0
                )
                assert (
                    executor.submit(docs.put, "module", "records", "id", {}, None)
                    .result(timeout=2)
                    .version
                    == 1
                )
            finally:
                release.set()
            reader.result(timeout=2)
        assert docs.count("module", "records", ()) == 1

    @pytest.mark.parametrize(
        "where",
        [
            [("x", "eq", "value")],
            [("x", "in", ["value", "other"])],
            [("x", "eq", None)],
        ],
    )
    def test_declared_indexes_accelerate_equality_and_in_queries(self, docs, where):
        docs.ensure_collection(
            "module",
            CollectionSpec(
                name="records",
                fields=(FieldSpec(name="x", type="string", indexed=True),),
            ),
        )
        for i in range(100):
            docs.put("module", "records", str(i), {"x": str(i) if i else None}, None)
        params = ["module", "records"]
        predicate = docs.predicates(where, params)
        with docs.transaction() as connection:
            connection.execute("ANALYZE")
            plan = connection.execute(
                "EXPLAIN QUERY PLAN SELECT id FROM abi_documents WHERE namespace = ? AND collection = ? AND ("  # nosec B608
                + predicate
                + ")",
                params,
            ).fetchall()  # nosec B608
        assert any("abi_doc_" in row[-1] and "<expr>=" in row[-1] for row in plan), plan

    @pytest.fixture
    def peer(self, tmp_path, adapter):
        peer = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        yield peer
        peer.close()

    @pytest.fixture
    def adapter(self, tmp_path):
        adapter = DocumentSecondaryAdapterSQLite(str(tmp_path / "documents.sqlite"))
        yield adapter
        adapter.close()


def test_udf_registration_failure_closes_connection(tmp_path):
    connection = Mock()
    connection.create_function.side_effect = RuntimeError("registration failed")
    with (
        patch("sqlite3.connect", return_value=connection),
        pytest.raises(RuntimeError, match="registration failed"),
    ):
        DocumentSecondaryAdapterSQLite(str(tmp_path / "failure.sqlite"))
    connection.close.assert_called_once()


def test_memory_adapter_persists_until_closed():
    adapter = DocumentSecondaryAdapterSQLite(":memory:")
    adapter.ensure_collection("module", CollectionSpec(name="records"))
    adapter.put("module", "records", "id", {}, None)
    assert adapter.get("module", "records", "id").version == 1
    adapter.close()
    adapter.close()
    with pytest.raises(RuntimeError, match="closed"):
        adapter.collections("module")


import sqlite3
