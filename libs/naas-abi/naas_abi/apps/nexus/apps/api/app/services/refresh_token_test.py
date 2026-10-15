from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.refresh_token import _as_naive_datetime


def test_as_naive_datetime_parses_sqlite_text():
    parsed = _as_naive_datetime("2026-10-18 15:14:07.702986")
    assert parsed == datetime(2026, 10, 18, 15, 14, 7, 702986)


def test_as_naive_datetime_accepts_datetime():
    value = datetime(2026, 10, 18, 15, 14, 7)
    assert _as_naive_datetime(value) == value


def test_as_naive_datetime_compares_to_now():
    now = datetime(2026, 10, 13, 17, 0, 0)
    assert _as_naive_datetime("2026-10-18 15:14:07.702986") > now
    assert _as_naive_datetime("2026-10-01 00:00:00") < now
