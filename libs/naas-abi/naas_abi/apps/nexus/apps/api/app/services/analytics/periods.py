"""Calendar periods of the scoped analytics, in the organization's time zone.

``today`` and ``yesterday`` are hourly, ``this_week`` (from Monday) and
``this_month`` (from the 1st) daily; the current periods end now. Boundaries
are computed with ``zoneinfo`` (daylight saving time included) and handed to
the tables as naive UTC, which is what they store.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from naas_abi.apps.nexus.apps.api.app.core.timezones import DEFAULT_TIMEZONE, valid_timezone
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import PeriodWindow, Slot

PERIODS: tuple[str, ...] = ("today", "yesterday", "this_week", "this_month")
__all__ = ["DEFAULT_TIMEZONE", "PERIODS", "resolve_period", "valid_timezone", "zone"]


def zone(name: str | None) -> ZoneInfo:
    """The zone named ``name``; UTC for an unknown or empty one."""
    return ZoneInfo(name) if name and valid_timezone(name) else ZoneInfo(DEFAULT_TIMEZONE)


def _naive_utc(moment: datetime) -> datetime:
    return moment.astimezone(UTC).replace(tzinfo=None)


def _local_midnight(day: datetime, tz: ZoneInfo) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=tz)


def _hourly(start: datetime, end: datetime, tz: ZoneInfo) -> list[Slot]:
    """Every local hour from ``start`` (aware) up to ``end``: stepped in UTC so a
    daylight saving change gives 23 or 25 slots, never a gap or an overlap."""
    slots: list[Slot] = []
    cursor = start.astimezone(UTC)
    stop = end.astimezone(UTC)
    while cursor < stop:
        following = cursor + timedelta(hours=1)
        slots.append(
            Slot(
                label=cursor.astimezone(tz).strftime("%Y-%m-%dT%H"),
                start=cursor.replace(tzinfo=None),
                end=following.replace(tzinfo=None),
            )
        )
        cursor = following
    return slots


def _daily(start: datetime, end: datetime, tz: ZoneInfo) -> list[Slot]:
    """Every local day from ``start`` (a local midnight) up to ``end``."""
    slots: list[Slot] = []
    day = start.astimezone(tz)
    while day.astimezone(UTC) < end.astimezone(UTC):
        following = _local_midnight(day.replace(tzinfo=None) + timedelta(days=1), tz)
        slots.append(
            Slot(
                label=day.strftime("%Y-%m-%d"),
                start=_naive_utc(day),
                end=_naive_utc(following),
            )
        )
        day = following
    return slots


def resolve_period(period: str, timezone: str | None, now: datetime | None = None) -> PeriodWindow:
    """The window of ``period`` in ``timezone`` at ``now`` (aware; the current time
    by default). ``ValueError`` for anything but the four periods."""
    if period not in PERIODS:
        raise ValueError(f"Unknown period {period!r}: one of {', '.join(PERIODS)}")
    tz = zone(timezone)
    name = timezone if timezone and valid_timezone(timezone) else DEFAULT_TIMEZONE
    current = (now or datetime.now(UTC)).astimezone(tz)
    today = _local_midnight(current, tz)

    if period == "today":
        start, end = today, current
    elif period == "yesterday":
        start = _local_midnight(today.replace(tzinfo=None) - timedelta(days=1), tz)
        end = today
    elif period == "this_week":
        start = _local_midnight(today.replace(tzinfo=None) - timedelta(days=today.weekday()), tz)
        end = current
    else:
        start = _local_midnight(today.replace(tzinfo=None).replace(day=1), tz)
        end = current

    hourly = period in ("today", "yesterday")
    if end <= start:
        # The very first instant of a period: one empty bucket rather than none.
        end = start + timedelta(seconds=1)
    slots = _hourly(start, end, tz) if hourly else _daily(start, end, tz)
    return PeriodWindow(
        period=period,
        timezone=name,
        start=_naive_utc(start),
        end=_naive_utc(end),
        local_start=start,
        local_end=end,
        granularity="hour" if hourly else "day",
        slots=tuple(slots),
    )
