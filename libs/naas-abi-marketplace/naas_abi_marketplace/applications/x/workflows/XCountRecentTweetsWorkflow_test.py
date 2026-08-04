"""Unit tests for XCountRecentTweetsWorkflow window logic.

These exercise the pure scheduling maths (no engine / no network): flooring to
the clock hour, ISO parsing, and the graph-driven gap resolution that decides
which complete hours are still missing and how far the in-progress partial
hour reaches.
"""

from datetime import UTC, datetime, timedelta

from naas_abi_marketplace.applications.x.workflows.XCountRecentTweetsWorkflow import (
    _MAX_LOOKBACK,
    XCountRecentTweetsWorkflow,
    _floor_hour,
    _parse_iso,
)

_NOW = datetime(2026, 7, 7, 14, 37, 12, tzinfo=UTC)
_H14 = datetime(2026, 7, 7, 14, 0, 0, tzinfo=UTC)


def _hours(*hours: int) -> set[datetime]:
    return {datetime(2026, 7, 7, h, 0, tzinfo=UTC) for h in hours}


def _full_retention_window() -> set[datetime]:
    """Every countable hour in the 7-day window ending at the in-progress hour."""
    hours: set[datetime] = set()
    cursor = _floor_hour(_NOW - _MAX_LOOKBACK) + timedelta(hours=1)
    while cursor < _H14:
        hours.add(cursor)
        cursor += timedelta(hours=1)
    return hours


def _workflow(stored: set[datetime], *, max_hours_per_run: int = 6):
    """A workflow whose graph lookups are stubbed to *stored* hour starts."""
    wf = XCountRecentTweetsWorkflow.__new__(XCountRecentTweetsWorkflow)

    class _Cfg:
        def __init__(self, max_hours_per_run: int) -> None:
            self.max_hours_per_run = max_hours_per_run

    # Name-mangled private attribute set by the real __init__.
    wf._XCountRecentTweetsWorkflow__configuration = _Cfg(max_hours_per_run)  # type: ignore[attr-defined]
    wf.stored_hour_starts = lambda query: stored  # type: ignore[method-assign]
    return wf


def test_floor_hour_truncates_to_clock_hour():
    assert _floor_hour(_NOW) == _H14
    assert _floor_hour(datetime(2026, 7, 7, 14, 59, 59, tzinfo=UTC)) == _H14
    assert _floor_hour(datetime(2026, 7, 7, 14, 0, 0, tzinfo=UTC)) == _H14


def test_parse_iso_handles_z_and_offset_and_naive():
    assert _parse_iso("2026-07-07T14:00:00Z") == _H14
    assert _parse_iso("2026-07-07T14:00:00+00:00") == _H14
    assert _parse_iso("2026-07-07T14:00:00").tzinfo is UTC
    assert _parse_iso("") is None
    assert _parse_iso("not-a-date") is None


def test_partial_window_covers_the_in_progress_hour_so_far():
    """Last tweet at 14:37 → the partial slice is 14:00 → 14:37."""
    wf = _workflow(set())
    start, end = wf._partial_window(_NOW)
    assert start == _H14
    assert end == _NOW


def test_newest_complete_hour_is_the_one_before_the_last_tweet():
    """A tweet at 14:37 makes 13:00-14:00 the newest countable full hour."""
    wf = _workflow(_full_retention_window() - _hours(13), max_hours_per_run=99)
    missing = wf._missing_hours("q", _NOW)
    assert missing == [datetime(2026, 7, 7, 13, 0, tzinfo=UTC)]
    # The in-progress hour is never requested as a complete hour.
    assert _H14 not in missing


def test_missing_hours_finds_interior_gaps_not_just_the_newest():
    """An outage leaves a hole that a resume-from-newest rule would skip."""
    wf = _workflow(_full_retention_window() - _hours(9, 10), max_hours_per_run=99)
    missing = wf._missing_hours("q", _NOW)
    assert missing == [
        datetime(2026, 7, 7, 9, 0, tzinfo=UTC),
        datetime(2026, 7, 7, 10, 0, tzinfo=UTC),
    ]


def test_missing_hours_is_capped_oldest_first():
    wf = _workflow(set(), max_hours_per_run=3)
    missing = wf._missing_hours("q", _NOW)
    assert len(missing) == 3
    assert missing == sorted(missing)
    # Oldest first: the cap starts at the retention edge, not at "now".
    assert missing[0] == _floor_hour(_NOW - _MAX_LOOKBACK) + timedelta(hours=1)


def test_missing_hours_empty_when_every_hour_is_stored():
    wf = _workflow(_full_retention_window(), max_hours_per_run=99)
    assert wf._missing_hours("q", _NOW) == []


def test_missing_hours_respects_seven_day_retention():
    wf = _workflow(set(), max_hours_per_run=999)
    missing = wf._missing_hours("q", _NOW)
    assert missing[0] >= _floor_hour(_NOW - _MAX_LOOKBACK)
    assert (_H14 - missing[0]) <= _MAX_LOOKBACK


def _workflow_with_partial(stored_end, *, partial_refresh_seconds: int = 600):
    """A workflow whose stored partial-slot end is stubbed."""
    wf = XCountRecentTweetsWorkflow.__new__(XCountRecentTweetsWorkflow)

    class _Cfg:
        def __init__(self, partial_refresh_seconds: int) -> None:
            self.partial_refresh_seconds = partial_refresh_seconds

    wf._XCountRecentTweetsWorkflow__configuration = _Cfg(partial_refresh_seconds)  # type: ignore[attr-defined]
    wf.stored_partial_end = lambda query: stored_end  # type: ignore[method-assign]
    return wf


def test_partial_refreshes_when_no_slot_stored_yet():
    assert _workflow_with_partial(None)._should_refresh_partial("q", _NOW) is True


def test_partial_refresh_skipped_while_slot_is_fresh():
    """12 minutes of ingestion, 10-minute throttle → still fresh at 5 minutes."""
    stored_end = datetime(2026, 7, 7, 14, 33, 0, tzinfo=UTC)
    wf = _workflow_with_partial(stored_end, partial_refresh_seconds=600)
    assert wf._should_refresh_partial("q", _NOW) is False


def test_partial_refreshes_once_the_slot_is_stale():
    stored_end = datetime(2026, 7, 7, 14, 20, 0, tzinfo=UTC)
    wf = _workflow_with_partial(stored_end, partial_refresh_seconds=600)
    assert wf._should_refresh_partial("q", _NOW) is True


def test_partial_always_refreshes_on_a_new_clock_hour():
    """A slot describing the previous hour must be replaced immediately."""
    stored_end = datetime(2026, 7, 7, 13, 59, 0, tzinfo=UTC)
    wf = _workflow_with_partial(stored_end, partial_refresh_seconds=99999)
    assert wf._should_refresh_partial("q", _NOW) is True
