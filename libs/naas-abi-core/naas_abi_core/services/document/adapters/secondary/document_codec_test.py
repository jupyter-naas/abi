import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from naas_abi_core.services.document.adapters.secondary.document_codec import (
    ValueKind,
    bytes_sort_key,
    decode,
    dumps,
    encode,
    encoded_bytes_sort_key,
    equality_key,
    sqlite_equal,
    sqlite_field,
    sqlite_json_key,
    storage_key,
    value_sort_parts,
)


def test_nested_tags_cannot_collide_with_user_objects():
    instant = datetime(2026, 1, 1, 3, tzinfo=timezone(timedelta(hours=3)))
    value = {
        "$t": "bytes",
        "$v": "not-base64",
        "$$t": "kept",
        "nested": [b"\x00\xff", instant],
    }
    result = decode(json.loads(dumps(encode(value))))
    assert result == value
    assert result["nested"][1].tzinfo == UTC
    assert type(result["nested"][0]) is bytes


def test_objects_are_unordered_but_arrays_and_scalar_types_are_distinct():
    assert dumps(encode({"z": 1, "a": {"y": 2, "b": 3}})) == dumps(
        encode({"a": {"b": 3, "y": 2}, "z": 1})
    )
    assert sqlite_equal('[1,{"a":2}]', '[1.0,{"a":2.0}]')
    assert not sqlite_equal("[1,2]", "[2,1]")
    assert not sqlite_equal("true", "1")
    assert equality_key({"x": [1.0, True]}) == {"x": [1, True]}
    assert sqlite_json_key("1.0") == sqlite_json_key("1")
    assert sqlite_json_key("true") != sqlite_json_key("1")


@pytest.mark.parametrize("key", ['a.b"\\\n', "$t", "", "caf\u00e9"])
def test_literal_field_accessor_distinguishes_missing_and_null(key):
    raw = dumps(encode({key: None}))
    assert sqlite_field(raw, storage_key(key)) == "null"
    assert sqlite_field(raw, "absent") is None


@pytest.mark.parametrize(
    "value", [b"", b"\x00", b"\x01", b"\xcf", b"\xd0", b"\xff\x00"]
)
def test_bytes_encoding_and_cursor_share_sort_key(value):
    expected = value.hex()
    assert bytes_sort_key(value) == expected
    assert encoded_bytes_sort_key(encode(value)["$v"]) == expected
    assert value_sort_parts(value) == (ValueKind.BYTES, 0, expected)
