"""Secondary adapter that persists analytics artifacts in ABI object storage.

Layout under ``naas_abi/nexus/analytics/``:

* ``events/<sha256>.pkl`` — one pickle per raw event (content-hashed key,
  so re-ingesting the same payload is naturally idempotent).
* ``<aggregate>.json`` — prebuilt aggregate consumed by the read endpoints
  (overview.json, users.json, sessions.json, pages.json, workspaces.json,
  user_details.json, recent_events.json, events.json, metadata.json,
  ref-users.json, ref-workspaces.json).
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.analytics.port import AnalyticsStoragePort
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from naas_abi_core.utils.StorageUtils import StorageUtils

OUTPUT_DIR = "naas_abi/nexus/analytics"
EVENTS_PREFIX = f"{OUTPUT_DIR}/events"


class AnalyticsSecondaryAdapterObjectStorage(AnalyticsStoragePort):
    def __init__(self, object_storage: ObjectStorageService) -> None:
        self._storage = object_storage
        self._utils = StorageUtils(storage_service=object_storage)

    # --- per-event pickle store --------------------------------------------

    def save_event(self, event: dict[str, Any]) -> str:
        digest = hashlib.sha256(pickle.dumps(event)).hexdigest()
        file_name = f"{digest}.pkl"
        self._utils.save_pickle(
            obj=event,
            dir_path=EVENTS_PREFIX,
            file_name=file_name,
            # Filename is already content-hashed; no audit copy needed.
            copy=False,
        )
        return f"{EVENTS_PREFIX}/{file_name}"

    def list_events(self) -> list[dict[str, Any]]:
        try:
            keys = self._storage.list_objects(prefix=EVENTS_PREFIX)
        except Exceptions.ObjectNotFound:
            return []

        events: list[dict[str, Any]] = []
        for full_key in keys:
            filename = os.path.basename(full_key)
            if not filename.endswith(".pkl"):
                continue
            event = self._utils.get_pickle(EVENTS_PREFIX, filename)
            if isinstance(event, dict):
                events.append(event)
            else:
                logger.debug(f"[analytics] skip {filename}: not a dict")
        return events

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
