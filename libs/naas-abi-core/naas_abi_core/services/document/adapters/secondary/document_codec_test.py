import json
from datetime import UTC, datetime, timedelta, timezone

import pytest
from naas_abi_core.services.document.adapters.secondary.document_codec import (
    ValueKind,
    bytes_sort_key,
    compare_numeric_text,
    decode,
    dumps,
    encode,
    encoded_bytes_sort_key,
    equality_key,
    sqlite_field,
    sqlite_json_key,
    sqlite_legacy_json_key,
    sqlite_numeric_text,
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
    assert sqlite_json_key('[1,{"a":2}]') == sqlite_json_key('[1.0,{"a":2.0}]')
    assert sqlite_json_key("[1,2]") != sqlite_json_key("[2,1]")
    assert equality_key({"x": [1.0, True]}) == {"x": [1, True]}
    assert sqlite_json_key("1.0") == sqlite_json_key("1")
    assert sqlite_json_key("true") != sqlite_json_key("1")


@pytest.mark.parametrize("value", [-(2**63), 2**63 - 1])
def test_decoding_preserves_signed_integer_boundaries(value):
    decoded = decode(value)
    assert type(decoded) is int
    assert decoded == value


def test_jsonb_expanded_float_is_restored_recursively():
    normalized = json.loads(
        '{"x":100000000000000000000,"nested":[-100000000000000000000]}'
    )
    decoded = decode(normalized)
    assert decoded == {"x": 1e20, "nested": [-1e20]}
    assert type(decoded["x"]) is float
    assert type(decoded["nested"][0]) is float


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


def test_numeric_keys_follow_json_decimal_not_binary_float_value():
    raw = "1.0000000000000001e18"
    assert sqlite_json_key(raw) == sqlite_json_key("1000000000000000100")
    assert sqlite_json_key(raw) != sqlite_json_key("1000000000000000128")
    assert compare_numeric_text(sqlite_numeric_text(raw), "1000000000000000100") == 0
    assert compare_numeric_text(sqlite_numeric_text(raw), "1000000000000000128") == -1
    assert compare_numeric_text("5e-324", "0") == 1
    assert decode(json.loads(raw)) == 1000000000000000100


def test_legacy_numeric_keys_remain_available_during_index_upgrade():
    assert sqlite_legacy_json_key("1.0000000000000001e18") == "1000000000000000128"
    assert sqlite_legacy_json_key("null") is None
    assert sqlite_legacy_json_key("[1.0, true, 1.5]") == "[1,true,1.5]"
