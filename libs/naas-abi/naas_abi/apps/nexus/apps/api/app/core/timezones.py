"""IANA time zones, as an organization's ``timezone`` names them."""

from __future__ import annotations

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DEFAULT_TIMEZONE = "UTC"


def valid_timezone(name: str | None) -> bool:
    """Whether ``name`` is an IANA time zone ``zoneinfo`` knows (``Europe/Paris``)."""
    if not name or not isinstance(name, str):
        return False
    try:
        ZoneInfo(name)
    except (ZoneInfoNotFoundError, ValueError):
        return False
    return True
