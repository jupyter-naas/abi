"""Calendar periods in the organization's time zone (epic #1533)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics.periods import (
    PERIODS,
    resolve_period,
    valid_timezone,
)

# Thursday 2026-11-19, 10:30 UTC (11:30 in Paris, 05:30 in New York).
NOW = datetime(2026, 11, 19, 10, 30, tzinfo=UTC)


def test_the_four_periods_are_the_only_ones() -> None:
    assert PERIODS == ("today", "yesterday", "this_week", "this_month")
    with pytest.raises(ValueError):
        resolve_period("last_7_days", "UTC", NOW)


def test_today_in_utc_is_hourly_from_midnight_to_now() -> None:
    window = resolve_period("today", "UTC", NOW)
    assert window.granularity == "hour"
    assert window.start == datetime(2026, 11, 19, 0, 0)
    assert window.end == datetime(2026, 11, 19, 10, 30)
    assert [s.label for s in window.slots][:2] == ["2026-11-19T00", "2026-11-19T01"]
    assert window.slots[-1].label == "2026-11-19T10"
    assert len(window.slots) == 11


def test_today_follows_the_organization_time_zone() -> None:
    window = resolve_period("today", "Europe/Paris", NOW)
    # Midnight in Paris is 23:00 UTC the day before (CET, UTC+1).
    assert window.start == datetime(2026, 11, 18, 23, 0)
    assert window.slots[0].label == "2026-11-19T00"
    assert window.slots[0].start == datetime(2026, 11, 18, 23, 0)
    assert window.info().date_start == "2026-11-19T00:00:00+01:00"
    assert window.info().timezone == "Europe/Paris"


def test_yesterday_is_the_whole_previous_local_day() -> None:
    window = resolve_period("yesterday", "America/New_York", NOW)
    # 05:30 in New York on the 19th: yesterday is the 18th, EST (UTC-5).
    assert window.start == datetime(2026, 11, 18, 5, 0)
    assert window.end == datetime(2026, 11, 19, 5, 0)
    assert len(window.slots) == 24
    assert window.slots[0].label == "2026-11-18T00"
    assert window.slots[-1].label == "2026-11-18T23"


def test_this_week_starts_on_monday_and_is_daily() -> None:
    window = resolve_period("this_week", "UTC", NOW)
    assert window.granularity == "day"
    assert window.start == datetime(2026, 11, 16, 0, 0)  # Monday
    assert window.end == datetime(2026, 11, 19, 10, 30)
    assert [s.label for s in window.slots] == [
        "2026-11-16",
        "2026-11-17",
        "2026-11-18",
        "2026-11-19",
    ]


def test_this_week_on_a_monday_is_one_day() -> None:
    monday = datetime(2026, 11, 16, 8, 0, tzinfo=UTC)
    assert [s.label for s in resolve_period("this_week", "UTC", monday).slots] == ["2026-11-16"]


def test_this_month_starts_on_the_first() -> None:
    window = resolve_period("this_month", "Europe/Paris", NOW)
    assert window.start == datetime(2026, 10, 31, 23, 0)
    assert window.slots[0].label == "2026-11-01"
    assert window.slots[-1].label == "2026-11-19"
    assert len(window.slots) == 19


def test_a_day_with_a_dst_change_has_23_hourly_slots() -> None:
    # Paris goes from CET to CEST on Sunday 2026-03-29 at 02:00.
    after = datetime(2026, 3, 30, 12, 0, tzinfo=UTC)
    window = resolve_period("yesterday", "Europe/Paris", after)
    assert len(window.slots) == 23
    assert window.end - window.start == datetime(2026, 1, 1, 23) - datetime(2026, 1, 1)
    # The daily buckets of the month cover the short day exactly.
    month = resolve_period("this_month", "Europe/Paris", after)
    sunday = next(s for s in month.slots if s.label == "2026-03-29")
    assert sunday.end - sunday.start == datetime(2026, 1, 1, 23) - datetime(2026, 1, 1)


def test_slots_tile_the_period() -> None:
    for period in PERIODS:
        window = resolve_period(period, "Asia/Tokyo", NOW)
        assert window.slots[0].start == window.start
        for previous, following in zip(window.slots, window.slots[1:], strict=False):
            assert previous.end == following.start
        assert window.slots[-1].end >= window.end


def test_valid_timezone() -> None:
    assert valid_timezone("Europe/Paris")
    assert valid_timezone("UTC")
    assert not valid_timezone("Mars/Olympus")
    assert not valid_timezone("")
    assert not valid_timezone("../../etc/passwd")
