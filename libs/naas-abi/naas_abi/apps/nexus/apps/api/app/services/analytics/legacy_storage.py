"""The removed analytics app's object-storage files: replayed into the rollups, then deleted.

Before epic #1533 the platform-wide analytics app kept, under ``naas_abi/nexus/analytics/``:

* ``events/<sha256>.json`` (``.pkl`` in older releases): one raw event per object,
  written when the deploy had no event log;
* its prebuilt aggregates and directories (``LEGACY_FILES``).

The backfill (``jobs.AnalyticsJobs.backfill``) replays every raw event, whatever its
age, into the rollups (``list_events``). Once it is done the cleanup
(``jobs.AnalyticsJobs.clean_legacy_storage``, once) replays them again (idempotent), then
deletes the aggregates and each raw event that was replayed (``delete_replayed``). A
file that could not be replayed (unreadable, not an event, refused by the rollups) is
never deleted: it is moved under ``UNREADABLE_PREFIX`` (``set_aside``) and logged.
Nothing writes these files any more.

Events are data: nothing read here is decoded as Python objects. An old pickle is
read with an unpickler that rebuilds plain containers and scalars only, and one that
names anything else is not an event (set aside, never run).

A failure to reach the storage raises, so the backfill is not recorded as done (and
nothing is deleted) until every event could be read.
"""

from __future__ import annotations

import io
import json
import logging
import os
import pickle  # nosec B403 - legacy events only, through _PlainUnpickler
from typing import Any

from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions

logger = logging.getLogger(__name__)

OUTPUT_DIR = "naas_abi/nexus/analytics"
EVENTS_PREFIX = f"{OUTPUT_DIR}/events"
# Where the raw events that could not be replayed are kept (by their file name).
UNREADABLE_PREFIX = f"{OUTPUT_DIR}/unreadable"
# What the app wrote beside ``events/``: deleted once the backfill is done.
LEGACY_FILES = (
    "events.json",
    "overview.json",
    "users.json",
    "sessions.json",
    "pages.json",
    "workspaces.json",
    "user_details.json",
    "recent_events.json",
    "ref-scenario.json",
    "ref-users.json",
    "ref-workspaces.json",
    "metadata.json",
)
# The largest legacy pickle read; analytics events are a few KiB.
LEGACY_EVENT_MAX_BYTES = 1 << 20

# A raw event's file name and its content as plain data (None: unreadable).
LegacyEvent = tuple[str, dict[str, Any] | None]


class _PlainUnpickler(pickle.Unpickler):  # nosec B301
    """Rebuilds dicts, lists, tuples, strings, numbers, booleans and None:
    the pickle opcodes for those name no global. Any global is refused."""

    def find_class(self, module: str, name: str) -> Any:
        raise pickle.UnpicklingError(f"legacy event names {module}.{name}")


def _plain_event(raw: bytes) -> dict[str, Any] | None:
    if len(raw) > LEGACY_EVENT_MAX_BYTES:
        return None
    try:
        event = _PlainUnpickler(io.BytesIO(raw)).load()
    except Exception:  # noqa: BLE001 - not a plain event: skipped, never run
        return None
    if not isinstance(event, dict):
        return None
    try:
        # What JSON keeps is what an event is.
        return json.loads(json.dumps(event))
    except (TypeError, ValueError):
        return None


def _json_event(raw: bytes) -> dict[str, Any] | None:
    try:
        event = json.loads(raw)
    except (TypeError, ValueError, UnicodeDecodeError):
        return None
    return event if isinstance(event, dict) else None


class LegacyAnalyticsStorage:
    """The legacy files in the engine's object storage (``ObjectStorageService``)."""

    def __init__(self, object_storage: Any) -> None:
        self._storage = object_storage

    def _event_names(self) -> list[str]:
        try:
            keys = self._storage.list_objects(prefix=EVENTS_PREFIX)
        except Exceptions.ObjectNotFound:
            return []
        return sorted({os.path.basename(str(key).rstrip("/")) for key in keys} - {""})

    def list_events(self) -> list[LegacyEvent]:
        """Every raw event file the app stored, with its event as plain data (None when
        it cannot be read as one)."""
        events: list[LegacyEvent] = []
        for name in self._event_names():
            if name.endswith(".json"):
                decode = _json_event
            elif name.endswith(".pkl"):
                decode = _plain_event
            else:
                decode = None
            try:
                raw = self._storage.get_object(EVENTS_PREFIX, name)
            except Exceptions.ObjectNotFound:
                continue
            event = decode(raw) if decode is not None and isinstance(raw, bytes) else None
            if event is None:
                logger.warning("[analytics] legacy event %s is not plain event data", name)
            events.append((name, event))
        return events

    def delete_replayed(self, names: list[str]) -> int:
        """Delete the aggregates and the raw events ``names`` (replayed); how many
        objects were deleted."""
        deleted = 0
        targets = [(OUTPUT_DIR, name) for name in LEGACY_FILES]
        targets += [(EVENTS_PREFIX, name) for name in names]
        for prefix, name in targets:
            try:
                self._storage.delete_object(prefix, name)
            except Exceptions.ObjectNotFound:
                continue
            deleted += 1
        return deleted

    def set_aside(self, names: list[str]) -> int:
        """Move the raw events ``names`` (not replayable) under ``UNREADABLE_PREFIX``,
        never deleting one that was not copied there; how many moved."""
        moved = 0
        for name in names:
            try:
                raw = self._storage.get_object(EVENTS_PREFIX, name)
                self._storage.put_object(UNREADABLE_PREFIX, name, raw)
            except Exceptions.ObjectNotFound:
                continue
            except Exception:  # noqa: BLE001 - kept where it is
                logger.warning(
                    "[analytics] legacy event %s could not be set aside; left in place",
                    name,
                    exc_info=True,
                )
                continue
            try:
                self._storage.delete_object(EVENTS_PREFIX, name)
            except Exceptions.ObjectNotFound:
                pass
            moved += 1
            logger.warning(
                "[analytics] legacy event %s could not be replayed; kept as %s/%s",
                name,
                UNREADABLE_PREFIX,
                name,
            )
        return moved
