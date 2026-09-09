from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import Mock

import pytest
from naas_abi_core.services.document.DocumentPort import (
    CollectionNotFound,
    CollectionSpec,
    Document,
    DocumentNotFound,
    IDocumentAdapter,
    Page,
    VersionConflict,
)
from naas_abi_core.services.document.DocumentService import DocumentService


@pytest.fixture
def adapter():
    return Mock(spec=IDocumentAdapter)


@pytest.fixture
def service(adapter):
    return DocumentService(adapter, namespace="my.module")


def test_namespace_is_bound_for_collection_and_document_operations(service, adapter):
    spec = CollectionSpec(name="records")
    service.ensure_collection(spec)
    adapter.ensure_collection.assert_called_once_with("my.module", spec)
    service.put("records", "id", {"n": 1}, if_version=4)
    adapter.put.assert_called_once_with("my.module", "records", "id", {"n": 1}, 4)
    service.get("records", "id")
    adapter.get.assert_called_once_with("my.module", "records", "id")
    service.delete("records", "id", if_version=5)
    adapter.delete.assert_called_once_with("my.module", "records", "id", 5)
    service.drop_collection("records")
    adapter.drop_collection.assert_called_once_with("my.module", "records")
    service.collections()
    adapter.collections.assert_called_once_with("my.module")


@pytest.mark.parametrize(
    "value",
    [
        datetime(2026, 1, 1),  # noqa: DTZ001 - exercise rejection of naive datetimes
        {"a": [datetime(2026, 1, 1)]},  # noqa: DTZ001 - exercise nested validation
        Decimal("1.2"),
        float("nan"),
        float("inf"),
        2**63,
        "\x00",
        {1: True},
        object(),
    ],
)
def test_invalid_values_fail_before_calling_adapter(service, adapter, value):
    with pytest.raises(ValueError):
        service.put("records", "id", {"value": value})
    adapter.put.assert_not_called()


@pytest.mark.parametrize(
    "options",
    [
        {"limit": 0},
        {"limit": True},
        {"order_by": ("x", "bad")},
        {"where": [("x", "raw_sql", "1=1")]},
        {"where": [("x", "exists", 1)]},
        {"where": [("x", "in", "text")]},
        {"where": [("x", "gt", {})]},
    ],
)
def test_invalid_queries_fail_before_calling_adapter(service, adapter, options):
    with pytest.raises(ValueError):
        service.find("records", **options)
    adapter.find.assert_not_called()


def test_exists_only_catches_document_not_found(service, adapter):
    adapter.get.side_effect = DocumentNotFound
    assert service.exists("records", "id") is False
    adapter.get.side_effect = CollectionNotFound
    with pytest.raises(CollectionNotFound):
        service.exists("records", "id")


def test_find_one_and_iteration_follow_opaque_cursors(service, adapter):
    now = datetime.now(UTC)
    one = Document("one", {}, now, now, 1)
    two = Document("two", {}, now, now, 2)
    adapter.find.side_effect = [Page([one], "opaque"), Page([two], None)]
    assert list(service.iterate("records", where=[("x", "exists", True)], batch=1)) == [
        one,
        two,
    ]
    assert adapter.find.call_args_list[1].args == (
        "my.module",
        "records",
        [("x", "exists", True)],
        None,
        1,
        "opaque",
    )
    adapter.find.side_effect = [Page([], None), Page([one], None)]
    assert service.find_one("records", ()) is None
    assert service.find_one("records", ()) == one


def test_bulk_delete_uses_versions_and_surfaces_concurrent_changes(service, adapter):
    now = datetime.now(UTC)
    adapter.find.return_value = Page([Document("id", {}, now, now, 7)], None)
    assert service.delete_many("records", ()) == 1
    adapter.delete.assert_called_once_with("my.module", "records", "id", 7)
    adapter.delete.side_effect = VersionConflict
    with pytest.raises(VersionConflict):
        service.delete_many("records", ())


def test_put_many_is_per_document_and_stops_on_failure(service, adapter):
    adapter.put.side_effect = ["first", VersionConflict]
    with pytest.raises(VersionConflict):
        service.put_many("records", {"a": {}, "b": {}, "c": {}})
    assert adapter.put.call_count == 2
