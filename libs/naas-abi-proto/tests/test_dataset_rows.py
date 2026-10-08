import json
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

import pytest

from naas_abi_proto.dataset.rows import decode_row, encode_row

BIG = 2**60 + 1


def test_rows_are_strict_json_with_exact_integers():
    row = {
        "id": BIG,
        "n": 42,
        "x": 1.0,
        "flag": True,
        "none": None,
        "text": "café",
        "payload": {"n": 42, "items": [1, 2.5]},
    }

    data = encode_row(row)

    assert json.loads(data) == row  # any JSON reader, not only Python's
    decoded = decode_row(data)
    assert decoded == row
    assert type(decoded["id"]) is int and type(decoded["x"]) is float


def test_values_without_a_json_form_take_their_portable_form():
    row = {
        "d": date(2026, 10, 4),
        "ts": datetime(2026, 10, 4, 12, 30, tzinfo=timezone.utc),
        "dec": Decimal("1.25"),
        "blob": b"\x00\xff",
        "id": uuid.UUID(int=1),
    }

    assert decode_row(encode_row(row)) == {
        "d": "2026-10-04",
        "ts": "2026-10-04T12:30:00+00:00",
        "dec": 1.25,
        "blob": "AP8=",
        "id": "00000000-0000-0000-0000-000000000001",
    }


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_non_finite_numbers_are_refused(value):
    with pytest.raises(ValueError):
        encode_row({"x": value})
    with pytest.raises(ValueError):
        encode_row({"payload": {"x": value}})
