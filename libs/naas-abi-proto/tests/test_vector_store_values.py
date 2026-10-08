import json
from datetime import date

import pytest

from naas_abi_proto.vector_store.v1 import vector_store_pb2
from naas_abi_proto.vector_store.values import (
    JSON_OBJECT_FIELDS,
    decode_object,
    encode_object,
)

BIG = 2**60 + 1


def test_objects_are_strict_json_with_exact_integers():
    value = {"n": 42, "big": BIG, "f": 1.5, "nested": {"items": [1, 2.5]}, "x": None}

    data = encode_object(value)

    assert json.loads(data) == value  # any JSON reader
    decoded = decode_object(data)
    assert decoded == value and type(decoded["big"]) is int


def test_empty_bytes_are_an_empty_object():
    assert decode_object(b"") == {}
    assert decode_object(encode_object({})) == {}


class _Scalar:
    """Stands in for a numpy scalar (the package does not depend on numpy)."""

    def __init__(self, value):
        self.value = value

    def item(self):
        return self.value


def test_values_without_a_json_form_take_a_portable_one():
    value = {"i": _Scalar(3), "f": _Scalar(0.5), "d": date(2026, 10, 4), "b": b"\x00\xff"}

    assert decode_object(encode_object(value)) == {
        "i": 3,
        "f": 0.5,
        "d": "2026-10-04",
        "b": "AP8=",
    }


def test_non_finite_numbers_and_non_objects_are_refused():
    with pytest.raises(ValueError):
        encode_object({"x": float("nan")})
    with pytest.raises(ValueError):
        decode_object(b"[1, 2]")


def test_the_registry_names_every_json_object_field_of_the_contract():
    named = set()
    for message in vector_store_pb2.DESCRIPTOR.message_types_by_name.values():
        for field in message.fields:
            if field.type == field.TYPE_BYTES and field.name in ("metadata", "payload", "filter"):
                named.add((message.full_name, field.name))
    assert named == {
        (message, field) for message, fields in JSON_OBJECT_FIELDS.items() for field in fields
    }
