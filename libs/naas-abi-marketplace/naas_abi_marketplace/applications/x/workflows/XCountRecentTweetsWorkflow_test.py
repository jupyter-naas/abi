"""Unit tests for XCountRecentTweetsWorkflow round-hour window logic.

These exercise the pure scheduling maths (no engine / no network): flooring to
the clock hour, ISO parsing, and the backfill / incremental / up-to-date window
resolution that keeps the hourly series fresh without recomputing history.
"""

from datetime import datetime, timedelta, timezone

from naas_abi_marketplace.applications.x.workflows.XCountRecentTweetsWorkflow import (
    XCountRecentTweetsWorkflow,
    _floor_hour,
    _parse_iso,
    _END_SAFETY,
    _MAX_LOOKBACK,
)

_NOW = datetime(2026, 7, 7, 14, 37, 12, tzinfo=timezone.utc)
_H14 = datetime(2026, 7, 7, 14, 0, 0, tzinfo=timezone.utc)


def _workflow_with_latest(latest):
    """A workflow instance whose stored latest-bucket lookup is stubbed."""
    wf = XCountRecentTweetsWorkflow.__new__(XCountRecentTweetsWorkflow)
    wf._latest_bucket_start = lambda query: latest  # type: ignore[method-assign]
    return wf


def test_floor_hour_truncates_to_clock_hour():
    assert _floor_hour(_NOW) == _H14
    assert _floor_hour(datetime(2026, 7, 7, 14, 59, 59, tzinfo=timezone.utc)) == _H14
    assert _floor_hour(datetime(2026, 7, 7, 14, 0, 0, tzinfo=timezone.utc)) == _H14


def test_parse_iso_handles_z_and_offset_and_naive():
    assert _parse_iso("2026-07-07T14:00:00Z") == _H14
    assert _parse_iso("2026-07-07T14:00:00+00:00") == _H14
    assert _parse_iso("2026-07-07T14:00:00").tzinfo is timezone.utc
    assert _parse_iso("") is None
    assert _parse_iso("not-a-date") is None


def test_window_end_is_round_hour_safely_in_the_past():
    end = _floor_hour(_NOW - _END_SAFETY)
    assert end == _H14
    assert end.minute == 0 and end.second == 0


def test_backfill_window_when_no_stored_buckets():
    wf = _workflow_with_latest(None)
    start, end, is_backfill = wf._resolve_window("q", _NOW)
    assert is_backfill is True
    assert end == _H14
    # Backfill starts just inside the 7-day retention window, on a round hour.
    assert start == _floor_hour(_NOW - _MAX_LOOKBACK) + timedelta(hours=1)
    assert start.minute == 0 and (end - start) <= _MAX_LOOKBACK


def test_incremental_window_resumes_after_last_stored_hour():
    wf = _workflow_with_latest(datetime(2026, 7, 7, 11, 0, tzinfo=timezone.utc))
    start, end, is_backfill = wf._resolve_window("q", _NOW)
    assert is_backfill is False
    assert start == datetime(2026, 7, 7, 12, 0, tzinfo=timezone.utc)
    assert end == _H14


def test_up_to_date_returns_none():
    # Last stored bucket is the hour right before end → nothing new to fetch.
    wf = _workflow_with_latest(datetime(2026, 7, 7, 13, 0, tzinfo=timezone.utc))
    assert wf._resolve_window("q", _NOW) is None
