"""Dataset rows over NATS: one JSON object per row, integers exact."""

import pytest
from naas_abi_core.proto.dataset.v1 import dataset_pb2
from naas_abi_core.services.dataset.adapters.dataset_row_codec import (
    decode_rows,
    encode_rows,
    query_result_from_pb,
    query_result_to_pb,
)
from naas_abi_core.services.dataset.DatasetPort import DatasetSchemaError, QueryResult

BIG = 2**60 + 1


def test_a_query_result_round_trips_exactly():
    result = QueryResult(
        columns=["id", "payload"], rows=[{"id": BIG, "payload": {"n": 42}}]
    )

    decoded = query_result_from_pb(
        dataset_pb2.QueryResult.FromString(
            query_result_to_pb(result).SerializeToString()
        )
    )

    assert decoded == result
    assert type(decoded.rows[0]["payload"]["n"]) is int


def test_write_rows_round_trip_and_refuse_non_finite_numbers():
    assert decode_rows(encode_rows([{"id": BIG}])) == [{"id": BIG}]
    with pytest.raises(DatasetSchemaError, match="Row 1 .* not finite"):
        encode_rows([{"x": 1.0}, {"x": float("nan")}])
