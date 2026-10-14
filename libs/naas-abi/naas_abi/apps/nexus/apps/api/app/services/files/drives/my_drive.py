"""Set up every user's My Drive: ``.manifest.json`` and the default folders.

``naas_abi/my-drive/<user_id>/`` gets:

- ``.manifest.json``, describing the user the drive belongs to, so it can be
  identified from object storage alone. It is rewritten when a field it holds
  (name, email) changes.
- ``downloads/``, ``documents/`` and ``uploads/`` (where chat attachments land).
  They are created once per user; a marker under
  ``naas_abi/.scaffolded/my-drive/`` records it, so a folder the user deletes is
  not brought back.

Users are created by several paths (signup, magic link, invites, config seeds),
so, like ``workspace_drive``, this listens to SQLAlchemy ORM sessions:
``after_flush`` stages, ``after_commit`` writes, ``after_rollback`` drops.
``backfill_my_drives`` does the same for users created before this existed.
Writing to the drive must never break a commit: a storage failure is logged.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    MODULE_ROOT,
    my_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.manifest import (
    MANIFEST_NAME,
    SCHEMA_VERSION,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.objects import (
    isoformat as _iso,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.objects import (
    object_exists as _exists,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy import event as sa_event
from sqlalchemy import inspect as sa_inspect
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

DEFAULT_FOLDERS = ("downloads", "documents", "uploads")
DEFAULT_FOLDERS_MARKER_ROOT = f"{MODULE_ROOT}/.scaffolded/my-drive"
# The user fields the manifest holds; a change to another one does not rewrite it.
_MANIFEST_FIELDS = ("name", "email")


def build_manifest(user: UserModel) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "user": {
            "id": user.id,
            "name": user.name,
            "email": user.email,
            "created_at": _iso(user.created_at),
            "updated_at": _iso(user.updated_at),
        },
    }


def write_manifest(storage: ObjectStorageService, manifest: dict[str, Any]) -> None:
    storage.put_object(
        my_drive_root(manifest["user"]["id"]),
        MANIFEST_NAME,
        json.dumps(manifest, indent=2).encode("utf-8"),
    )


def create_default_folders(storage: ObjectStorageService, user_id: str) -> None:
    """Create the default folders, keeping anything already there."""
    root = my_drive_root(user_id)
    for folder in DEFAULT_FOLDERS:
        prefix = f"{root}/{folder}"
        if not _exists(storage, prefix, FilesService.folder_marker):
            storage.put_object(prefix, FilesService.folder_marker, b"")
    storage.put_object(DEFAULT_FOLDERS_MARKER_ROOT, user_id, b"")


async def backfill_my_drives(
    session: AsyncSession, storage: ObjectStorageService
) -> dict[str, int]:
    """Write the missing manifests and default folders. Returns how many of each were written."""
    users = (await session.execute(select(UserModel))).scalars().all()
    manifests = [build_manifest(user) for user in users]

    def _write_missing() -> dict[str, int]:
        written = {"manifests": 0, "default_folders": 0}
        for manifest in manifests:
            user_id = manifest["user"]["id"]
            try:
                if not _exists(storage, my_drive_root(user_id), MANIFEST_NAME):
                    write_manifest(storage, manifest)
                    written["manifests"] += 1
                if not _exists(storage, DEFAULT_FOLDERS_MARKER_ROOT, user_id):
                    create_default_folders(storage, user_id)
                    written["default_folders"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[my-drive] backfill failed for {user_id}: {exc}")
        return written

    return await asyncio.to_thread(_write_missing)


def _manifest_fields_changed(user: UserModel) -> bool:
    state = sa_inspect(user)
    return any(state.attrs[field].history.has_changes() for field in _MANIFEST_FIELDS)


class MyDriveWriter:
    """Install/uninstall the ORM listeners. One instance per object storage."""

    _key = "my_drives"

    def __init__(self, get_storage: Callable[[], ObjectStorageService]) -> None:
        # Resolved at commit time: the engine's storage may not exist at install time.
        self._get_storage = get_storage

    def _listeners(self) -> tuple[tuple[str, Callable[..., Any]], ...]:
        return (
            ("after_flush", self._after_flush),
            ("after_commit", self._after_commit),
            ("after_rollback", self._after_rollback),
        )

    def install(self) -> None:
        for name, fn in self._listeners():
            if not sa_event.contains(Session, name, fn):
                sa_event.listen(Session, name, fn)

    def uninstall(self) -> None:
        for name, fn in self._listeners():
            if sa_event.contains(Session, name, fn):
                sa_event.remove(Session, name, fn)

    def _after_flush(self, session: Session, _flush_context: Any) -> None:
        try:
            created = [obj for obj in session.new if isinstance(obj, UserModel)]
            updated = [
                obj
                for obj in session.dirty
                if isinstance(obj, UserModel) and _manifest_fields_changed(obj)
            ]
            if not created and not updated:
                return
            # Keyed by id: the last flush of a transaction holds the committed values,
            # and a user created earlier in the transaction stays "created".
            staged = session.info.setdefault(self._key, {})
            for user in created:
                staged[user.id] = (build_manifest(user), True)
            for user in updated:
                was_created = staged.get(user.id, (None, False))[1]
                staged[user.id] = (build_manifest(user), was_created)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[my-drive] could not stage users: {exc}")

    def _after_commit(self, session: Session) -> None:
        pending: dict[str, tuple[dict[str, Any], bool]] = session.info.pop(self._key, {})
        if not pending:
            return
        try:
            storage = self._get_storage()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[my-drive] object storage unavailable: {exc}")
            return
        for user_id, (manifest, created) in pending.items():
            try:
                write_manifest(storage, manifest)
                if created:
                    create_default_folders(storage, user_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[my-drive] write failed for {user_id}: {exc}")

    def _after_rollback(self, session: Session) -> None:
        session.info.pop(self._key, None)
