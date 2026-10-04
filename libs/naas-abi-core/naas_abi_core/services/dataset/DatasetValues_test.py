import uuid
from datetime import date, datetime, time, timedelta, timezone
from decimal import Decimal

import pytest
from naas_abi_core.services.dataset.DatasetValues import (
    is_finite,
    row_value,
    timestamp_value,
)

BIG = 2**60 + 1


@pytest.mark.parametrize(
    "value",
    [None, True, 42, BIG, 1.5, "café", {"n": 42, "items": [1, 2.5]}],
)
def test_json_values_are_kept_as_they_are(value):
    assert row_value(value) == value
    assert type(row_value(value)) is type(value)


@pytest.mark.parametrize(
    ("value", "portable"),
    [
        (date(2026, 10, 4), "2026-10-04"),
        (datetime(2026, 10, 4, 12, 30), "2026-10-04T12:30:00"),
        (
            datetime(2026, 10, 4, 12, 30, tzinfo=timezone.utc),
            "2026-10-04T12:30:00+00:00",
        ),
        (time(12, 30), "12:30:00"),
        (Decimal("1.25"), 1.25),
        (Decimal("12"), 12.0),
        (b"\x00\xff", "AP8="),
        (uuid.UUID(int=1), "00000000-0000-0000-0000-000000000001"),
        (float("nan"), None),
        (float("inf"), None),
        (Decimal("NaN"), None),
        ((1, date(2026, 10, 4)), [1, "2026-10-04"]),
        ({"at": date(2026, 10, 4), "x": float("nan")}, {"at": "2026-10-04", "x": None}),
    ],
)
def test_other_values_take_their_portable_form(value, portable):
    assert row_value(value) == portable
    assert type(row_value(value)) is type(portable)


def test_finite_numbers():
    assert is_finite(1.5) and is_finite(42) and is_finite("NaN")
    assert not is_finite(float("nan")) and not is_finite(-float("inf"))
    assert not is_finite(Decimal("Infinity"))


@pytest.mark.parametrize(
    ("value", "stored"),
    [
        (
            datetime(2026, 10, 4, 12, 30, tzinfo=timezone(timedelta(hours=2))),
            datetime(2026, 10, 4, 10, 30),
        ),
        ("2026-10-04T12:30:00+02:00", datetime(2026, 10, 4, 10, 30)),
        ("2026-10-04T10:30:00Z", datetime(2026, 10, 4, 10, 30)),
        (datetime(2026, 10, 4, 10, 30), datetime(2026, 10, 4, 10, 30)),
        ("2026-10-04T10:30:00", "2026-10-04T10:30:00"),
        ("not a time", "not a time"),
        (None, None),
    ],
)
def test_timestamps_are_stored_in_utc_without_an_offset(value, stored):
    assert timestamp_value(value) == stored
