"""Secondary adapter that keeps raw analytics events in the EventService log.

Replaces one object-storage PUT per tracker event with one append to the
durable event log. Aggregates stay in object storage — they are a read cache
the frontend fetches by key — so this adapter delegates every JSON operation to
the object-storage adapter it wraps.

Migration is read-through, not a cutover: ``list_events`` returns the union of
the event log and the legacy ``events/<sha256>.pkl`` objects, deduplicated by
payload content. Existing history therefore stays visible with nothing to
backfill, and the pickle store simply stops growing.

The log is append-only, so it never holds an email: ``save_event`` keeps the
user id and drops ``user_email`` from both the column and the stored payload.
``list_events`` puts it back from the service's user directory
(``ref-users.json``, mutable, so an address can be changed or erased there).
Legacy pickles keep the email they were written with.
"""

from __future__ import annotations

import hashlib
import json
import threading
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.adapters.secondary.analytics__secondary_adapter__object_storage import (  # noqa: E501
    AnalyticsSecondaryAdapterObjectStorage,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.ontologies.AnalyticsEventOntology import (
    AnalyticsEventRecorded,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsStoragePort
from naas_abi.apps.nexus.apps.api.app.services.analytics.service import REF_USERS_FILE
from naas_abi_core import logger

# The legacy pickles are frozen the moment this adapter is in use: nothing
# writes another one. Reading them once per process turns what was a LIST plus
# one GET per event on every rebuild into a single cold-start cost.
_legacy_cache: list[dict[str, Any]] | None = None
_legacy_lock = threading.Lock()


def reset_legacy_cache() -> None:
    """Drop the cached legacy events. For tests and manual re-reads."""
    global _legacy_cache
    with _legacy_lock:
        _legacy_cache = None


def _content_key(event: dict[str, Any]) -> str:
    """Identity of an event by content, matching the pickle store's hashing.

    The legacy adapter derived each filename from a hash of the payload, so
    re-ingesting an identical event was a no-op. ``publish`` always appends, so
    the same rule is applied on read instead — which also collapses an event
    that exists both in the log and as a legacy pickle.
    """
    # Without the email: the log copy of a legacy pickle no longer carries it.
    content = {k: v for k, v in event.items() if k != "user_email"}
    return hashlib.sha256(json.dumps(content, sort_keys=True, default=str).encode("utf-8")).hexdigest()


class AnalyticsSecondaryAdapterEventLog(AnalyticsStoragePort):
    def __init__(
        self,
        events: Any,
        object_storage_adapter: AnalyticsSecondaryAdapterObjectStorage,
    ) -> None:
        self._events = events
        self._json = object_storage_adapter

    # --- raw events ---------------------------------------------------------

    def save_event(self, event: dict[str, Any]) -> str:
        event = {k: v for k, v in event.items() if k != "user_email"}
        record = AnalyticsEventRecorded(
            event_id=event.get("event_id"),
            timestamp=event.get("timestamp"),
            event_name=event.get("event_name"),
            user_id=event.get("user_id"),
            workspace_id=event.get("workspace_id"),
            session_id=event.get("session_id"),
            page_path=event.get("page_path"),
            payload_json=json.dumps(event, sort_keys=True, default=str),
        )
        stored = self._events.publish(record)
        return f"event-log#seq={getattr(stored, 'seq', None)}"

    def _legacy_events(self) -> list[dict[str, Any]]:
        global _legacy_cache
        with _legacy_lock:
            if _legacy_cache is not None:
                return _legacy_cache
        try:
            loaded = self._json.list_events()
        except Exception as exc:
            # History is a nice-to-have; a storage hiccup must not empty the
            # dashboards of everything the log already holds.
            logger.warning(f"[analytics] legacy event read failed: {exc}")
            return []
        with _legacy_lock:
            _legacy_cache = loaded
        return loaded

    def list_events(self) -> list[dict[str, Any]]:
        merged: dict[str, dict[str, Any]] = {
            _content_key(event): event for event in self._legacy_events()
        }
        for record in self._events.iter_query(event_class=AnalyticsEventRecorded):
            raw = getattr(record, "payload_json", None)
            if not raw:
                continue
            try:
                payload = json.loads(raw)
            except (TypeError, ValueError) as exc:
                logger.debug(f"[analytics] skip unreadable event payload: {exc}")
                continue
            if isinstance(payload, dict):
                # A legacy pickle of the same event carries its email; keep it.
                merged.setdefault(_content_key(payload), payload)
        emails = self._user_emails()
        out: list[dict[str, Any]] = []
        for payload in merged.values():
            if "user_email" not in payload and payload.get("user_id") in emails:
                payload = {**payload, "user_email": emails[payload["user_id"]]}
            out.append(payload)
        return out

    def _user_emails(self) -> dict[str, str]:
        try:
            users = self._json.load_json(REF_USERS_FILE, fallback=[])
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[analytics] user directory unavailable: {exc}")
            return {}
        if not isinstance(users, list):
            return {}
        return {
            str(u["user_id"]): str(u["user_email"])
            for u in users
            if isinstance(u, dict) and u.get("user_id") and u.get("user_email")
        }

    # --- JSON aggregates ----------------------------------------------------

    def save_json(self, file_name: str, data: Any) -> None:
        self._json.save_json(file_name, data)

    def load_json(self, file_name: str, fallback: Any = None) -> Any:
        return self._json.load_json(file_name, fallback)
