"""Keeping the analytics rollups: what the consumer, the backfill and the purge do.

The tracker's events are recorded once in the EventService log
(``AnalyticsEventRecorded``). One consumer cursor (``CONSUMER_ID``) reads each new
event and hands it here: its raw row (kept ``RETENTION_DAYS``), its hourly count
and its session are written by ``AnalyticsEventPort.apply_events``, which skips
an event it has already applied. The backfill replays, once, what the log holds
within the retention window and every legacy object-storage event whatever its age
(``apply_legacy``: rollups only for those past retention); the purge deletes, daily,
the raw rows past it (the rollups stay).

Events are client data: their strings lose control characters (PostgreSQL refuses a
NUL in text) and their timestamps are read defensively (``parse_timestamp``), so no
event can make a whole batch fail. The ingest accepts timestamps within
[now - ``RETENTION_DAYS``, now + ``FUTURE_TOLERANCE``] (``event_time_accepted``), and
nothing later than ``FUTURE_TOLERANCE`` from now is applied.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Iterable
from datetime import UTC, datetime, timedelta
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsEvent,
    AnalyticsEventPort,
    RecordedEvent,
)

RETENTION_DAYS = 45
# How far ahead of the server's clock an event may be (a client's clock drift).
FUTURE_TOLERANCE = timedelta(days=1)
# The single cursor of the log's analytics events, shared by every API process:
# each batch it reads is one process's alone.
CONSUMER_ID = "nexus.analytics.rollups"
BACKFILL_JOB = "backfill_v1"
PURGE_JOB = "purge_raw_events"
PURGE_EVERY_SECONDS = 24 * 3600.0


# C0 controls (NUL included), DEL and lone UTF-16 surrogates: none is wanted in an
# analytics string, PostgreSQL refuses a NUL in text and UTF-8 has no surrogate.
_CONTROL = re.compile(r"[\x00-\x1f\x7f\ud800-\udfff]")


def parse_timestamp(value: Any) -> datetime | None:
    """A tracker timestamp (ISO-8601, ``Z`` or an offset) as naive UTC; None if unreadable
    (including one whose UTC value falls outside the years 1-9999)."""
    if isinstance(value, datetime):
        moment = value
    elif isinstance(value, str) and value:
        try:
            moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except (ValueError, OverflowError):
            return None
    else:
        return None
    if moment.tzinfo is not None:
        try:
            moment = moment.astimezone(UTC).replace(tzinfo=None)
        except (ValueError, OverflowError, OSError):
            return None
    return moment


def event_time_accepted(moment: datetime | None, now: datetime) -> bool:
    """Whether the ingest takes an event of ``moment`` (naive UTC) at ``now``: within
    the raw events' retention and at most ``FUTURE_TOLERANCE`` ahead."""
    if moment is None:
        return False
    current = now.astimezone(UTC).replace(tzinfo=None) if now.tzinfo else now
    return current - timedelta(days=RETENTION_DAYS) <= moment <= current + FUTURE_TOLERANCE


def strip_control(value: Any) -> Any:
    """``value`` with the control characters removed from every string in it (dict
    keys, lists and nested values included)."""
    if isinstance(value, str):
        return _CONTROL.sub("", value)
    if isinstance(value, dict):
        return {strip_control(k): strip_control(v) for k, v in value.items()}
    if isinstance(value, list | tuple):
        return [strip_control(v) for v in value]
    return value


def _text(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    return _CONTROL.sub("", value) or None


def recorded_from_payload(payload: dict[str, Any]) -> RecordedEvent | None:
    """A stored tracker payload (the log's ``payload_json``, a legacy event) as the
    rollups apply it; None for one missing what every event has. Emails are dropped."""
    if not isinstance(payload, dict):
        return None
    timestamp = parse_timestamp(payload.get("timestamp"))
    event_id = _text(payload.get("event_id"))
    session_id = _text(payload.get("session_id"))
    event_name = _text(payload.get("event_name"))
    if timestamp is None or not event_id or not session_id or not event_name:
        return None
    return RecordedEvent(
        event_id=event_id,
        timestamp=timestamp,
        session_id=session_id,
        event_name=event_name,
        user_id=_text(payload.get("user_id")),
        workspace_id=_text(payload.get("workspace_id")),
        organization_id=_text(payload.get("organization_id")),
        page_path=_text(payload.get("page_path")),
        page_title=_text(payload.get("page_title")),
        device=_text(payload.get("device")),
        browser=_text(payload.get("browser")),
        payload=strip_control({k: v for k, v in payload.items() if k != "user_email"}),
    )


def recorded_from_event(event: AnalyticsEvent) -> RecordedEvent | None:
    return recorded_from_payload(event.model_dump(exclude_none=True))


def applicable(payload: Any, now: datetime) -> bool:
    """Whether the rollups apply ``payload`` at ``now`` (whatever its age): an event
    with what every event has, not later than ``FUTURE_TOLERANCE`` ahead."""
    recorded = recorded_from_payload(payload)
    current = now.astimezone(UTC).replace(tzinfo=None) if now.tzinfo else now
    return recorded is not None and recorded.timestamp <= current + FUTURE_TOLERANCE


def payload_of_log_event(record: Any) -> dict[str, Any] | None:
    """The tracker payload of an ``AnalyticsEventRecorded`` read from the log, with
    the organization its column carries."""
    raw = getattr(record, "payload_json", None)
    if not raw:
        return None
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(payload, dict):
        return None
    organization = getattr(record, "organization_id", None)
    if organization and not payload.get("organization_id"):
        payload["organization_id"] = organization
    return payload


class AnalyticsRollups:
    def __init__(
        self,
        events: AnalyticsEventPort,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.events = events
        self._now = now or (lambda: datetime.now(UTC))

    def _naive_now(self) -> datetime:
        return self._now().astimezone(UTC).replace(tzinfo=None)

    def retention_cutoff(self) -> datetime:
        return self._naive_now() - timedelta(days=RETENTION_DAYS)

    def _not_after(self) -> datetime:
        return self._naive_now() + FUTURE_TOLERANCE

    def _applicable(self, payloads: Iterable[dict[str, Any]]) -> list[RecordedEvent]:
        latest = self._not_after()
        return [
            r
            for r in map(recorded_from_payload, payloads)
            if r is not None and r.timestamp <= latest
        ]

    async def apply(self, payloads: Iterable[dict[str, Any]]) -> int:
        """Apply tracker payloads (new ones only, within retention): how many were new."""
        recorded = self._applicable(payloads)
        if not recorded:
            return 0
        return await self.events.apply_events(recorded, not_before=self.retention_cutoff())

    async def apply_legacy(self, payloads: Iterable[dict[str, Any]]) -> int:
        """Apply the removed app's events whatever their age: the raw row only for those
        within retention, the rollups for all. Each is counted once, however many
        times it is replayed."""
        recorded = self._applicable(payloads)
        if not recorded:
            return 0
        return await self.events.apply_legacy_events(recorded, raw_since=self.retention_cutoff())

    async def apply_recorded(self, events: list[RecordedEvent]) -> int:
        latest = self._not_after()
        events = [e for e in events if e.timestamp <= latest]
        if not events:
            return 0
        return await self.events.apply_events(events, not_before=self.retention_cutoff())

    async def backfill_pending(self) -> bool:
        return await self.events.job_last_run(BACKFILL_JOB) is None

    async def claim_backfill(self) -> bool:
        """Whether this process runs the backfill now: it is pending and no other
        process started it within the hour (one that died is taken over then)."""
        if not await self.backfill_pending():
            return False
        return await self.events.claim_job(
            f"{BACKFILL_JOB}.running", now=self._naive_now(), every=3600.0
        )

    async def purge(self) -> int | None:
        """Once a day across processes: delete the raw events past retention. None
        when another run was recent."""
        if not await self.events.claim_job(
            PURGE_JOB, now=self._naive_now(), every=PURGE_EVERY_SECONDS
        ):
            return None
        return await self.events.purge_events(self.retention_cutoff())
