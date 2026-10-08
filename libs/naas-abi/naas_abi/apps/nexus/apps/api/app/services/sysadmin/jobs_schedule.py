"""Next ticks and plain-English descriptions of job triggers (pure functions).

Crons have 6 fields with seconds first, as NATS message schedules do
(``"0 30 9 * * mon-fri"``), or an alias (``"@daily"``). A cron without a time
zone runs in UTC. Day of month and day of week combine with cron's OR rule when
both are restricted. Intervals are Go durations (``"1h30m"``).
"""

from __future__ import annotations

import re
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from naas_abi.apps.nexus.apps.api.app.services.sysadmin.jobs import TriggerSpec

ALIASES = {
    "@yearly": "0 0 0 1 1 *",
    "@annually": "0 0 0 1 1 *",
    "@monthly": "0 0 0 1 * *",
    "@weekly": "0 0 0 * * 0",
    "@daily": "0 0 0 * * *",
    "@midnight": "0 0 0 * * *",
    "@hourly": "0 0 * * * *",
}

MONTH_NAMES = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
DAY_NAMES = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"]
MONTH_LABELS = [n.capitalize() for n in MONTH_NAMES]
DAY_LABELS = ["Sunday", "Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday"]

# (low, high, names) per field: second minute hour day-of-month month day-of-week
FIELDS: list[tuple[int, int, list[str] | None]] = [
    (0, 59, None),
    (0, 59, None),
    (0, 23, None),
    (1, 31, None),
    (1, 12, MONTH_NAMES),
    (0, 7, DAY_NAMES),
]

SEARCH_YEARS = 5
_DURATION_PART = re.compile(r"(\d+(?:\.\d+)?)(ns|us|µs|ms|s|m|h)")
_DURATION = re.compile(r"(?:\d+(?:\.\d+)?(?:ns|us|µs|ms|s|m|h))+")
_UNITS = {"ns": 1e-9, "us": 1e-6, "µs": 1e-6, "ms": 1e-3, "s": 1, "m": 60, "h": 3600}


class _Invalid(ValueError):
    pass


def _value(token: str, low: int, names: list[str] | None) -> int:
    token = token.lower()
    if names and token in names:
        return names.index(token) + (low if names is MONTH_NAMES else 0)
    if not token.isdigit():
        raise _Invalid(token)
    return int(token)


def _field(text: str, low: int, high: int, names: list[str] | None) -> tuple[frozenset[int], bool]:
    """The values a field allows, and whether it restricts anything."""
    if text in ("*", "?"):
        return frozenset(range(low, high + 1)), False
    values: set[int] = set()
    for part in text.split(","):
        base, _, step_text = part.partition("/")
        step = int(step_text) if step_text else 1
        if step_text and (not step_text.isdigit() or step < 1):
            raise _Invalid(part)
        if base in ("*", "?"):
            start, end = low, high
        elif "-" in base:
            first, _, last = base.partition("-")
            start, end = _value(first, low, names), _value(last, low, names)
        else:
            start = _value(base, low, names)
            end = high if step_text else start
        if not (low <= start <= high and low <= end <= high) or start > end:
            raise _Invalid(part)
        values.update(range(start, end + 1, step))
    return frozenset(values), True


def _parse(expression: str) -> list[tuple[frozenset[int], bool]]:
    text = ALIASES.get(expression.strip().lower(), expression.strip())
    if text.startswith("@"):
        raise _Invalid(text)
    parts = text.split()
    if len(parts) != 6:
        raise _Invalid(text)
    fields = [_field(p, *spec) for p, spec in zip(parts, FIELDS, strict=True)]
    days, restricted = fields[5]
    # 7 is Sunday too.
    fields[5] = (frozenset(0 if d == 7 else d for d in days), restricted)
    return fields


def _zone(time_zone: str) -> ZoneInfo:
    return ZoneInfo(time_zone) if time_zone else ZoneInfo("UTC")


def next_cron(expression: str, time_zone: str, after: datetime) -> datetime | None:
    """The first time strictly after ``after`` the cron fires, in UTC; None if invalid."""
    try:
        fields = _parse(expression)
        zone = _zone(time_zone)
    except (_Invalid, ValueError, ZoneInfoNotFoundError):
        return None

    seconds, minutes, hours = fields[0][0], fields[1][0], fields[2][0]
    (doms, dom_set), months, (dows, dow_set) = fields[3], fields[4][0], fields[5]

    def day_ok(day: datetime) -> bool:
        dow = (day.weekday() + 1) % 7
        if dom_set and dow_set:
            return day.day in doms or dow in dows
        return day.day in doms and dow in dows

    reference = after.astimezone(UTC)
    # Wall-clock search in the trigger's zone, starting at the next whole second.
    current = (reference.astimezone(zone).replace(microsecond=0) + timedelta(seconds=1)).replace(
        tzinfo=None
    )
    limit = current + timedelta(days=366 * SEARCH_YEARS)
    while current < limit:
        if current.month not in months:
            year = current.year + (current.month == 12)
            month = current.month % 12 + 1
            current = datetime(year, month, 1)
            continue
        if not day_ok(current):
            current = datetime(current.year, current.month, current.day) + timedelta(days=1)
            continue
        if current.hour not in hours:
            current = current.replace(minute=0, second=0) + timedelta(hours=1)
            continue
        if current.minute not in minutes:
            current = current.replace(second=0) + timedelta(minutes=1)
            continue
        if current.second not in seconds:
            current = current + timedelta(seconds=1)
            continue
        found = current.replace(tzinfo=zone).astimezone(UTC)
        if found > reference:
            return found
        current = current + timedelta(seconds=1)
    return None


def go_duration_seconds(interval: str) -> float | None:
    if not _DURATION.fullmatch(interval or ""):
        return None
    return sum(float(n) * _UNITS[u] for n, u in _DURATION_PART.findall(interval))


def next_every(
    interval: str, last_fired: datetime | None, *, now: datetime | None = None
) -> datetime | None:
    """The last fire plus the interval (rolled forward past ``now``); None without a fire."""
    seconds = go_duration_seconds(interval)
    if last_fired is None or not seconds:
        return None
    step = timedelta(seconds=seconds)
    found = last_fired.astimezone(UTC) + step
    if now is not None and found <= now:
        missed = int((now - found) / step) + 1
        found += step * missed
    return found


# --- describe ------------------------------------------------------------------------------


def _ordinal(n: int) -> str:
    suffix = "th" if 11 <= n % 100 <= 13 else {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def _every(seconds: float) -> str:
    for size, one in ((86_400, "day"), (3600, "hour"), (60, "minute"), (1, "second")):
        if seconds >= size and seconds % size == 0:
            count = int(seconds // size)
            if count == 1:
                return f"Every {one}"
            if size == 3600 and count % 24 == 0:
                continue
            return f"Every {count} {one}s"
    return f"Every {seconds:g} seconds"


def _single(text: str) -> int | None:
    return int(text) if text.isdigit() else None


def _step(text: str) -> int | None:
    match = re.fullmatch(r"\*/(\d+)", text)
    return int(match.group(1)) if match else None


def _zone_suffix(time_zone: str) -> str:
    if time_zone in ("", "UTC", "Etc/UTC", "Z"):
        return " UTC"
    return f" ({time_zone})"


def _days(values: frozenset[int]) -> str:
    if values == frozenset({1, 2, 3, 4, 5}):
        return "weekdays"
    if values == frozenset({0, 6}):
        return "weekends"
    names = [DAY_LABELS[d] for d in sorted(values)]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + f" and {names[-1]}"


def _describe_cron(expression: str, time_zone: str) -> str:
    fallback = f"Cron {expression}"
    raw = ALIASES.get(expression.strip().lower(), expression.strip())
    parts = raw.split()
    if len(parts) != 6:
        return fallback
    try:
        fields = _parse(raw)
    except _Invalid:
        return fallback
    sec, minute, hour, dom, month, dow = parts
    s, m, h = _single(sec), _single(minute), _single(hour)
    all_days = dom in ("*", "?") and month in ("*", "?") and dow in ("*", "?")
    zone = _zone_suffix(time_zone)

    if s is not None and m is not None and h is not None:
        clock = f"{h:02d}:{m:02d}" + (f":{s:02d}" if s else "")
        if all_days:
            return f"Every day at {clock}{zone}"
        if dom in ("*", "?") and month in ("*", "?"):
            days = fields[5][0]
            if days == frozenset({0}) and dow in ("0", "7", "sun"):
                return f"Every Sunday at {clock}{zone}"
            return f"At {clock} on {_days(days)}{zone}"
        day = _single(dom)
        if day is not None and dow in ("*", "?"):
            if month in ("*", "?"):
                return f"On the {_ordinal(day)} of every month at {clock}{zone}"
            month_value = _single(month)
            if month_value is None and month.lower() in MONTH_NAMES:
                month_value = MONTH_NAMES.index(month.lower()) + 1
            if month_value is not None:
                return f"Every year on {MONTH_LABELS[month_value - 1]} {day} at {clock}{zone}"
        return fallback
    if not all_days:
        return fallback
    if h is None and hour == "*" and m is not None and s == 0:
        return f"Every hour at :{m:02d}"
    if hour == "*" and minute == "*" and s is not None:
        return "Every minute" if s == 0 else f"Every minute at second {s}"
    if hour == "*" and _step(minute) and s == 0:
        return _every(_step(minute) * 60)  # type: ignore[operator]
    if hour == "*" and minute == "*" and _step(sec):
        return _every(_step(sec))  # type: ignore[arg-type]
    if _step(hour) and m == 0 and s == 0:
        return _every(_step(hour) * 3600)  # type: ignore[operator]
    return fallback


def describe(trigger: TriggerSpec) -> str:
    """A trigger in plain English, falling back to its raw spec."""
    if trigger.kind == "cron":
        return _describe_cron(trigger.spec, trigger.time_zone)
    if trigger.kind == "every":
        seconds = go_duration_seconds(trigger.spec)
        return _every(seconds) if seconds else f"Every {trigger.spec}"
    if trigger.kind == "event":
        match = re.fullmatch(r"evt\.([0-9a-f]+)\.>", trigger.spec)
        if match:
            return f"On event evt.{match.group(1)[:4]}…"
        return f"On NATS subject {trigger.spec}"
    return trigger.spec
