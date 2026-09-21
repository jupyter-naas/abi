"""Draft working copies in the engine object store.

``<root>/<workspace>/<slug>/files/<path>`` holds the files,
``index.json`` their sizes (one read lists a project, even on S3), and
``state.json`` the service's save state.
"""

from __future__ import annotations

import json
import threading
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.apps.projects.port import (
    AppDraftStorePort,
    AppFile,
    AppProjectKey,
    workspace_segment,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import (
    ObjectStorageService,
)

DEFAULT_ROOT = "nexus/app-projects"
_INDEX = "index.json"
_STATE = "state.json"


class AppDraftStoreObjectStorage(AppDraftStorePort):
    def __init__(self, storage: ObjectStorageService, root: str = DEFAULT_ROOT) -> None:
        self.storage = storage
        self.root = root.strip("/")
        self._lock = threading.Lock()

    def _prefix(self, key: AppProjectKey) -> str:
        return f"{self.root}/{workspace_segment(key.workspace_id)}/{key.slug}"

    def _files_prefix(self, key: AppProjectKey) -> str:
        return f"{self._prefix(key)}/files"

    def _read_json(self, key: AppProjectKey, name: str) -> dict[str, Any] | None:
        try:
            raw = self.storage.get_object(self._prefix(key), name)
        except Exceptions.ObjectNotFound:
            return None
        try:
            data = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _write_json(self, key: AppProjectKey, name: str, data: dict[str, Any]) -> None:
        self.storage.put_object(self._prefix(key), name, json.dumps(data).encode("utf-8"))

    def read_state(self, key: AppProjectKey) -> dict[str, Any] | None:
        return self._read_json(key, _STATE)

    def write_state(self, key: AppProjectKey, state: dict[str, Any]) -> None:
        self._write_json(key, _STATE, state)

    def _index(self, key: AppProjectKey) -> dict[str, int]:
        index = self._read_json(key, _INDEX)
        if index is not None:
            return {str(p): int(s) for p, s in index.items()}
        # Rebuild from a listing (lost index, or files written by hand).
        prefix = self._files_prefix(key)
        try:
            keys = self.storage.list_objects_recursive(prefix)
        except Exceptions.ObjectNotFound:
            return {}
        rebuilt: dict[str, int] = {}
        for full in keys:
            rel = full.split(f"{prefix}/", 1)[-1]
            try:
                rebuilt[rel] = len(self.storage.get_object(prefix, rel))
            except Exceptions.ObjectNotFound:
                continue
        return rebuilt

    def list_files(self, key: AppProjectKey) -> list[AppFile]:
        return [AppFile(path, size) for path, size in sorted(self._index(key).items())]

    def read_file(self, key: AppProjectKey, path: str) -> bytes | None:
        try:
            return self.storage.get_object(self._files_prefix(key), path)
        except Exceptions.ObjectNotFound:
            return None

    def write_file(self, key: AppProjectKey, path: str, data: bytes) -> None:
        with self._lock:
            self.storage.put_object(self._files_prefix(key), path, data)
            index = self._index(key)
            index[path] = len(data)
            self._write_json(key, _INDEX, index)

    def delete_file(self, key: AppProjectKey, path: str) -> None:
        with self._lock:
            try:
                self.storage.delete_object(self._files_prefix(key), path)
            except Exceptions.ObjectNotFound:
                pass
            index = self._index(key)
            index.pop(path, None)
            self._write_json(key, _INDEX, index)

    def clear(self, key: AppProjectKey) -> None:
        with self._lock:
            self._clear(key)

    def replace_all(self, key: AppProjectKey, files: dict[str, bytes]) -> None:
        with self._lock:
            self._clear(key)
            for path, data in files.items():
                self.storage.put_object(self._files_prefix(key), path, data)
            self._write_json(key, _INDEX, {p: len(d) for p, d in files.items()})

    def _clear(self, key: AppProjectKey) -> None:
        for path in self._index(key):
            try:
                self.storage.delete_object(self._files_prefix(key), path)
            except Exceptions.ObjectNotFound:
                pass
        for name in (_INDEX, _STATE):
            try:
                self.storage.delete_object(self._prefix(key), name)
            except Exceptions.ObjectNotFound:
                pass
