from datetime import UTC, datetime

import numpy as np
import pytest
from naas_abi_core.services.vector_store.adapters.vector_store_nats_codec import (
    document_to_pb,
    object_to_pb,
    pb_to_document,
    pb_to_search_result,
    search_result_to_pb,
)
from naas_abi_core.services.vector_store.IVectorStorePort import (
    SearchResult,
    VectorDocument,
)

METADATA = {
    "beyond_int64": 2**64 + 1,  # JSON keeps any integer exact
    "above_double_precision": 2**53 + 1,
    "ratio": 0.1,
    "flag": True,
    "nothing": None,
    "nested": {"tags": ["a", {"b": [1, None]}], "empty": {}},
}


def _over_the_wire(message):
    return type(message).FromString(message.SerializeToString())


def test_a_document_round_trips_with_exact_integers_and_nested_values():
    vector = np.array([0.5, -1.25, 3.0], dtype=np.float32)
    document = VectorDocument("doc-1", vector, METADATA, {"body": {"n": 2**62}})

    decoded = pb_to_document(_over_the_wire(document_to_pb(document)))

    assert decoded.id == "doc-1"
    assert decoded.vector.dtype == np.float32
    assert np.array_equal(decoded.vector, vector)
    assert decoded.metadata == METADATA
    assert type(decoded.metadata["above_double_precision"]) is int
    assert type(decoded.metadata["flag"]) is bool
    assert decoded.payload == {"body": {"n": 2**62}}


def test_an_absent_payload_stays_none_and_an_empty_one_stays_empty():
    vector = np.array([1.0], dtype=np.float32)

    absent = pb_to_document(
        _over_the_wire(document_to_pb(VectorDocument("a", vector, {})))
    )
    empty = pb_to_document(
        _over_the_wire(document_to_pb(VectorDocument("e", vector, {}, {})))
    )

    assert absent.payload is None and absent.metadata == {}
    assert empty.payload == {}


def test_a_search_result_round_trips_and_keeps_its_absent_fields_absent():
    full = SearchResult(
        "doc-1", 0.875, np.array([0.25, 2.0], dtype=np.float32), METADATA, {"k": [1]}
    )
    bare = SearchResult("doc-2", 0.5)

    decoded_full = pb_to_search_result(_over_the_wire(search_result_to_pb(full)))
    decoded_bare = pb_to_search_result(_over_the_wire(search_result_to_pb(bare)))

    assert decoded_full.score == 0.875
    assert np.array_equal(decoded_full.vector, full.vector)
    assert decoded_full.metadata == METADATA
    assert decoded_full.payload == {"k": [1]}
    assert decoded_bare == SearchResult("doc-2", 0.5)


def test_values_without_a_json_form_take_a_portable_one():
    at = datetime(2026, 10, 6, 9, 30, tzinfo=UTC)
    metadata = {"raw": b"\x00\xff", "at": at, "count": np.int64(2**62)}

    decoded = pb_to_document(
        _over_the_wire(
            document_to_pb(VectorDocument("d", np.array([1.0], np.float32), metadata))
        )
    )

    assert decoded.metadata == {
        "raw": "AP8=",  # base64
        "at": "2026-10-06T09:30:00+00:00",
        "count": 2**62,
    }


def test_nan_has_no_json_form_and_is_refused():
    with pytest.raises(ValueError):
        object_to_pb({"x": float("nan")})
