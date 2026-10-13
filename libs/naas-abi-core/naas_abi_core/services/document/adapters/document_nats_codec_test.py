from datetime import UTC, datetime, timedelta, timezone

import pytest
from naas_abi_core.services.document.adapters.document_nats_codec import (
    decode_document,
    decode_order,
    decode_spec,
    decode_where,
    encode_document,
    encode_spec,
    encode_where,
)
from naas_abi_core.services.document.DocumentPort import (
    CollectionSpec,
    Document,
    FieldSpec,
)
from naas_abi_proto.document.v1 import document_pb2 as pb

PARIS = timezone(timedelta(hours=2))


def _over_the_wire(message):
    return type(message).FromString(message.SerializeToString())


def _document(data):
    return Document(
        "doc-1",
        data,
        datetime(2026, 10, 6, 9, 30, tzinfo=UTC),
        datetime(2026, 10, 6, 11, 45, 12, 345678, tzinfo=PARIS),
        2**40,
    )


def test_a_document_round_trips_with_every_value_kind():
    data = {
        "int64_max": 2**63 - 1,
        "int64_min": -(2**63),
        "above_double_precision": 2**53 + 1,
        "float": 0.1,
        "flag": True,
        "nothing": None,
        "text": "héllo ✓",
        "raw": b"\x00\xffbytes",
        "at": datetime(2026, 1, 2, 3, 4, 5, 6, tzinfo=UTC),
        "nested": {"list": [1, "two", None, [3.5, {"deep": False}]], "empty": {}},
    }

    decoded = decode_document(_over_the_wire(encode_document(_document(data))))

    assert decoded == _document(data)
    assert decoded.data["int64_max"] == 2**63 - 1
    assert decoded.data["above_double_precision"] == 2**53 + 1
    # bool and int stay distinct (True == 1 in Python, so compare types).
    assert type(decoded.data["flag"]) is bool
    assert type(decoded.data["above_double_precision"]) is int
    assert type(decoded.data["raw"]) is bytes


def test_datetimes_keep_their_instant_and_come_back_in_utc():
    local = datetime(2026, 10, 6, 11, 45, tzinfo=PARIS)

    decoded = decode_document(_over_the_wire(encode_document(_document({"at": local}))))

    assert decoded.data["at"] == local
    assert decoded.data["at"].utcoffset() == timedelta(0)
    assert decoded.updated_at == _document({}).updated_at


def test_values_the_wire_cannot_hold_exactly_are_refused():
    with pytest.raises(ValueError):  # beyond sint64: refused, never truncated
        encode_document(_document({"n": 2**63}))
    with pytest.raises(ValueError, match="timezone-aware"):
        encode_document(_document({"at": datetime(2026, 1, 1)}))  # noqa: DTZ001
    with pytest.raises(ValueError):
        encode_document(_document({"x": float("nan")}))


def test_a_collection_spec_round_trips():
    spec = CollectionSpec(
        name="runs",
        fields=(
            FieldSpec(name="job", type="string", indexed=True),
            FieldSpec(name="attempt", type="int"),
            FieldSpec(name="key", type="string", unique=True),
        ),
        unique_together=(("job", "attempt"),),
    )

    assert decode_spec(_over_the_wire(encode_spec(spec))) == spec


def test_predicates_and_order_round_trip():
    where = (
        ("n", "gte", 2**62),
        ("status", "in", ["RUNNING", "RETRYING"]),
        ("meta", "eq", {"nested": [1, None]}),
        ("deleted_at", "exists", None),
    )
    request = pb.FindRequest(
        where=encode_where(where), order_by=pb.OrderBy(field="n", direction="desc")
    )

    decoded = _over_the_wire(request)

    assert decode_where(decoded.where) == where
    assert decode_order(decoded) == ("n", "desc")
    assert decode_order(pb.FindRequest()) is None
