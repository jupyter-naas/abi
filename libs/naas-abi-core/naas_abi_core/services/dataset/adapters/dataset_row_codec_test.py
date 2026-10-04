"""Dataset rows on the wire: exact JSON rows, with Struct kept for older peers."""

from datetime import date
from decimal import Decimal
from unittest.mock import Mock

from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.adapters.dataset_row_codec import (
    decode_row,
    encode_row,
    query_result_from_pb,
    query_result_to_pb,
    write_rows_from_pb,
    write_rows_to_pb,
)
from naas_abi_core.services.dataset.adapters.primary.dataset__primary_adapter__NATS import (
    DatasetPrimaryAdapterNATS,
)
from naas_abi_core.services.dataset.DatasetPort import DatasetInfo, QueryResult

BIG = 2**60 + 1


def test_rows_keep_integers_exact_and_other_values_readable():
    row = {
        "id": BIG,
        "n": 42,
        "f": 1.5,
        "flag": True,
        "none": None,
        "nested": {"n": 42, "items": [1, 2.5]},
        "when": date(2026, 10, 4),
        "amount": Decimal("12"),
        "price": Decimal("1.25"),
        "blob": b"\x00\xff",
        "text": "café",
    }
    decoded = decode_row(encode_row(row))

    assert decoded["id"] == BIG and type(decoded["id"]) is int
    assert decoded["n"] == 42 and type(decoded["n"]) is int
    assert decoded["nested"] == {"n": 42, "items": [1, 2.5]}
    assert decoded["when"] == "2026-10-04"
    assert decoded["amount"] == 12 and type(decoded["amount"]) is int
    assert decoded["price"] == 1.25
    assert decoded["blob"] == "AP8="  # base64
    assert decoded["text"] == "café"


def test_a_query_result_is_json_rows_for_a_caller_that_asks_and_struct_otherwise():
    result = QueryResult(columns=["id"], rows=[{"id": BIG}])

    modern = query_result_to_pb(result, json_rows=True)
    legacy = query_result_to_pb(result, json_rows=False)

    assert list(modern.rows) == [] and len(modern.json_rows) == 1
    assert list(legacy.json_rows) == [] and len(legacy.rows) == 1
    assert query_result_from_pb(modern).rows == [{"id": BIG}]
    # An older server only sends Struct rows: still read, as doubles.
    assert query_result_from_pb(legacy).rows == [{"id": float(BIG)}]


def test_a_write_carries_both_encodings_and_prefers_json_rows():
    request = dataset_pb2.WriteRequest()
    write_rows_to_pb(request, [{"id": BIG}])

    # Both: an older server, which ignores json_rows, still writes the rows.
    assert len(request.rows) == 1 and len(request.json_rows) == 1
    assert write_rows_from_pb(request) == [{"id": BIG}]
    # An older client sends Struct rows only.
    older = dataset_pb2.WriteRequest()
    older.rows.add().update({"id": 42})
    assert write_rows_from_pb(older) == [{"id": 42.0}]


def _primary(adapter):
    primary = DatasetPrimaryAdapterNATS.__new__(DatasetPrimaryAdapterNATS)
    primary._adapter = adapter
    return primary


def test_the_primary_answers_in_the_encoding_the_request_asked_for():
    adapter = Mock()
    adapter.query.return_value = QueryResult(columns=["id"], rows=[{"id": BIG}])
    primary = _primary(adapter)

    asked = primary._call_query(
        dataset_pb2.QueryRequest(sql="x", accept_json_rows=True)
    )
    older = primary._call_query(dataset_pb2.QueryRequest(sql="x"))

    assert len(asked.query_result.json_rows) == 1 and not asked.query_result.rows
    assert len(older.query_result.rows) == 1 and not older.query_result.json_rows


def test_the_primary_writes_exact_rows_from_json_rows():
    adapter = Mock()
    adapter.write.return_value = DatasetInfo(
        name="t",
        namespace="default",
        columns=(),
        partitions=(),
        primary_key=(),
        snapshot_id=1,
        location="memory://t",
    )
    primary = _primary(adapter)
    request = dataset_pb2.WriteRequest(name="t")
    write_rows_to_pb(request, [{"id": BIG}])

    primary._call_write(request)

    assert adapter.write.call_args.args[1] == [{"id": BIG}]
