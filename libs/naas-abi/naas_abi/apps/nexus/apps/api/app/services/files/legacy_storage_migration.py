"""Lazy migration from the legacy storage layout to the naas_abi/ rooted layout.

Older deployments stored files directly under the datastore root:

    my-drive/<user_id>/...
    <workspace_id>/...

The new layout nests everything under a per-module ``naas_abi/`` directory:

    naas_abi/my-drive/<user_id>/...
    naas_abi/workspace-drive/<workspace_id>/...

This module moves a user's or workspace's files on first access. Each migration
is guarded by a marker object stored under ``naas_abi/.migrated/`` so the move
runs at most once per entity. The whole module is intentionally temporary.

TODO(remove-after: all live deployments have been migrated and the on-disk
legacy paths are confirmed empty): delete this file and its call sites.
"""

from __future__ import annotations

import logging
from collections import deque

from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import (
    MODULE_ROOT,
    my_drive_root,
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

logger = logging.getLogger(__name__)

_MARKER_ROOT = f"{MODULE_ROOT}/.migrated"


class LegacyStorageMigrator:
    def __init__(self, files_service: FilesService) -> None:
        self.files_service = files_service
        self.storage: ObjectStorageService = files_service.storage

    def ensure_my_drive_migrated(self, user_id: str) -> None:
        marker = f"{_MARKER_ROOT}/my-drive/{user_id}"
        self._migrate_once(
            marker_path=marker,
            legacy_root=f"my-drive/{user_id}",
            new_root=my_drive_root(user_id),
        )

    def ensure_workspace_drive_migrated(self, workspace_id: str) -> None:
        marker = f"{_MARKER_ROOT}/workspace-drive/{workspace_id}"
        self._migrate_once(
            marker_path=marker,
            legacy_root=workspace_id,
            new_root=workspace_drive_root(workspace_id),
        )

    def _migrate_once(self, marker_path: str, legacy_root: str, new_root: str) -> None:
        if self._marker_exists(marker_path):
            return

        try:
            self._move_tree(legacy_root, new_root)
        except Exception as exc:  # noqa: BLE001 — temporary migration code
            logger.warning(
                "Legacy storage migration failed for %s -> %s: %s",
                legacy_root,
                new_root,
                exc,
            )
            return

        self._write_marker(marker_path)

    def _move_tree(self, legacy_root: str, new_root: str) -> None:
        """Recursively move all files under ``legacy_root`` to ``new_root``.

        Empty directories under the legacy root are not preserved (the storage
        layer has no first-class notion of directories — a directory exists by
        virtue of holding files).
        """
        try:
            top_level = self.storage.list_objects(legacy_root)
        except Exceptions.ObjectNotFound:
            return

        queue: deque[str] = deque(top_level)
        while queue:
            entry = queue.popleft()
            relative = entry[len(legacy_root) + 1 :] if entry.startswith(f"{legacy_root}/") else entry

            try:
                children = self.storage.list_objects(entry)
                queue.extend(children)
                continue
            except Exceptions.ObjectNotFound:
                continue
            except (NotADirectoryError, OSError):
                # ``entry`` is a leaf file
                pass

            prefix, key = self._split(entry)
            new_full = f"{new_root}/{relative}"
            new_prefix, new_key = self._split(new_full)

            try:
                content = self.storage.get_object(prefix, key)
            except Exceptions.ObjectNotFound:
                continue

            if self._object_exists(new_prefix, new_key):
                # Destination already populated for this exact path — leave both
                # in place so an operator can reconcile, but keep going.
                logger.warning(
                    "Skipping legacy migration of %s — destination %s already exists",
                    entry,
                    new_full,
                )
                continue

            self.storage.put_object(new_prefix, new_key, content)
            try:
                self.storage.delete_object(prefix, key)
            except Exceptions.ObjectNotFound:
                pass

    @staticmethod
    def _split(path: str) -> tuple[str, str]:
        if "/" not in path:
            return "", path
        prefix, key = path.rsplit("/", 1)
        return prefix, key

    def _object_exists(self, prefix: str, key: str) -> bool:
        try:
            self.storage.get_object(prefix, key)
            return True
        except Exceptions.ObjectNotFound:
            return False

    def _marker_exists(self, marker_path: str) -> bool:
        prefix, key = self._split(marker_path)
        return self._object_exists(prefix, key)

    def _write_marker(self, marker_path: str) -> None:
        prefix, key = self._split(marker_path)
        self.storage.put_object(prefix, key, b"")
