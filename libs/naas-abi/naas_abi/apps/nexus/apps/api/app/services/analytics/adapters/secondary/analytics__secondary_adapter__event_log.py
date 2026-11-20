"""Secondary adapter that records the tracker's events in the EventService log.

Each ingested event becomes one ``AnalyticsEventRecorded``, with the columns the
log can be queried by projected beside the payload. The rollups' consumer
(``analytics/jobs.py``) reads them back through its cursor.

The log is append-only, so it never holds an email: ``save_event`` drops
``user_email`` from both the columns and the stored payload. Emails are read from
the users table when the analytics are read.
"""

from __future__ import annotations

import json
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsEventLogPort


class AnalyticsSecondaryAdapterEventLog(AnalyticsEventLogPort):
    def __init__(self, events: Any) -> None:
        self._events = events

    def save_event(self, event: dict[str, Any]) -> str:
        event = {k: v for k, v in event.items() if k != "user_email"}
        record = AnalyticsEventRecorded(
            event_id=event.get("event_id"),
            timestamp=event.get("timestamp"),
            event_name=event.get("event_name"),
            user_id=event.get("user_id"),
            workspace_id=event.get("workspace_id"),
            organization_id=event.get("organization_id"),
            session_id=event.get("session_id"),
            page_path=event.get("page_path"),
            payload_json=json.dumps(event, sort_keys=True, default=str),
        )
        stored = self._events.publish(record)
        return f"event-log#seq={getattr(stored, 'seq', None)}"
