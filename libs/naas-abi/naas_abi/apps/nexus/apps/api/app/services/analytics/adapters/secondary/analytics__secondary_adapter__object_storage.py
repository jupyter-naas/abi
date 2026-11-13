"""Secondary adapter that persists analytics artifacts in ABI object storage.

Layout under ``naas_abi/nexus/analytics/``:

* ``events/<sha256>.json`` — one JSON object per raw event (content-hashed
  key, so re-ingesting the same payload is naturally idempotent).
* ``<aggregate>.json`` — prebuilt aggregate consumed by the read endpoints
  (overview.json, users.json, sessions.json, pages.json, workspaces.json,
  user_details.json, recent_events.json, events.json, metadata.json,
  ref-users.json, ref-workspaces.json).

Events are data: nothing read from storage is decoded as Python objects.
Older releases wrote ``events/<sha256>.pkl`` pickles. ``list_events`` converts
each to ``.json`` once, reading it with an unpickler that rebuilds plain
containers and scalars only, and skips any that names anything else.
"""

from __future__ import annotations

import hashlib
import io
import json
import os
import pickle  # nosec B403 - legacy events only, through _PlainUnpickler
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsStoragePort
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_core.utils.StorageUtils import StorageUtils

OUTPUT_DIR = "naas_abi/nexus/analytics"
EVENTS_PREFIX = f"{OUTPUT_DIR}/events"
# The largest legacy pickle converted; analytics events are a few KiB.
LEGACY_EVENT_MAX_BYTES = 1 << 20


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


def _event_bytes(event: dict[str, Any]) -> bytes:
    return json.dumps(event, sort_keys=True, ensure_ascii=False).encode("utf-8")


class AnalyticsSecondaryAdapterObjectStorage(AnalyticsStoragePort):
    def __init__(self, object_storage: ObjectStorageService) -> None:
        self._storage = object_storage
        self._utils = StorageUtils(storage_service=object_storage)

    # --- per-event JSON store -----------------------------------------------

    def save_event(self, event: dict[str, Any]) -> str:
        content = _event_bytes(event)
        file_name = f"{hashlib.sha256(content).hexdigest()}.json"
        self._storage.put_object(prefix=EVENTS_PREFIX, key=file_name, content=content)
        return f"{EVENTS_PREFIX}/{file_name}"

    def list_events(self) -> list[dict[str, Any]]:
        try:
            keys = self._storage.list_objects(prefix=EVENTS_PREFIX)
        except Exceptions.ObjectNotFound:
            return []

        events: list[dict[str, Any]] = []
        for full_key in keys:
            filename = os.path.basename(full_key)
            if filename.endswith(".json"):
                event = self._read_event(filename)
            elif filename.endswith(".pkl"):
                event = self._convert_legacy_event(filename)
            else:
                continue
            if isinstance(event, dict):
                events.append(event)
            else:
                logger.debug(f"[analytics] skip {filename}: not an event")
        return events

    def _read_event(self, filename: str) -> Any:
        try:
            return json.loads(self._storage.get_object(EVENTS_PREFIX, filename))
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[analytics] skip unreadable {filename}: {exc}")
            return None

    def _convert_legacy_event(self, filename: str) -> dict[str, Any] | None:
        """A legacy pickle, as JSON, written back as ``.json`` and removed."""
        try:
            raw = self._storage.get_object(EVENTS_PREFIX, filename)
        except Exception as exc:  # noqa: BLE001
            logger.debug(f"[analytics] skip unreadable {filename}: {exc}")
            return None
        event = _plain_event(raw) if isinstance(raw, bytes) else None
        if event is None:
            logger.warning(f"[analytics] legacy event {filename} is not plain data; skipped")
            return None
        try:
            self.save_event(event)
            self._storage.delete_object(EVENTS_PREFIX, filename)
        except Exception as exc:  # noqa: BLE001 - converted again next time
            logger.debug(f"[analytics] legacy event {filename} not converted: {exc}")
        return event

    # --- JSON aggregates ----------------------------------------------------

    def save_json(self, file_name: str, data: Any) -> None:
        self._utils.save_json(
            data=data,
            dir_path=OUTPUT_DIR,
            file_name=file_name,
            copy=False,
        )

    def load_json(self, file_name: str, fallback: Any = None) -> Any:
        try:
            raw = self._storage.get_object(OUTPUT_DIR, file_name)
            if raw is None:
                return fallback
            return json.loads(raw.decode("utf-8"))
        except Exception as exc:
            logger.debug(f"[analytics] {file_name} not present in storage: {exc}")
            return fallback
