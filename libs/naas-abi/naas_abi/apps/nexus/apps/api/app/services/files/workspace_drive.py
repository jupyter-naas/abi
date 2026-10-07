"""Set up every workspace's drive: ``manifest.json`` and the staff system folders.

``naas_abi/workspace-drive/<workspace_id>/`` gets:

- ``.manifest.json``, describing the workspace the folder belongs to, so the
  drive can be identified from object storage alone (a backup, the system
  drive, another tool reading the bucket). It is rewritten whenever the
  workspace is updated.
- one folder per staff system function (``personnel/``, ``intelligence/``, ...
  ``external/``), each with a ``README.md`` explaining what to file there. The
  texts live in ``apps/nexus/assets/staff_folders/``. They are created once per
  workspace; a marker under ``naas_abi/.scaffolded/staff-folders/`` records it,
  so a folder a user deletes is not brought back.

Workspaces are created and edited by several paths: the workspaces API, public
signup and magic-link signup (a personal workspace), and the config seeds at
boot. Like ``identity_events.capture``, this listens to SQLAlchemy ORM sessions
rather than instrumenting each one:

- ``after_flush``: created or updated ``WorkspaceModel`` rows are read and staged.
- ``after_commit``: manifests (and, for new workspaces, the staff folders) are written.
- ``after_rollback``: they are dropped, so a change that did not happen is not written.

``backfill_workspace_drives`` does the same for workspaces created before this
existed. Writing to the drive must never break a commit: a storage failure is logged.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from datetime import datetime
from functools import cache
from pathlib import Path
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.files.drive_roots import (
    MODULE_ROOT,
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

MANIFEST_NAME = ".manifest.json"
# The first version wrote it without the leading dot; backfill removes those.
LEGACY_MANIFEST_NAME = "manifest.json"
SCHEMA_VERSION = 1

README_NAME = "README.md"
# The nine staff system functions, S1 to S9.
STAFF_FOLDERS = (
    "personnel",
    "intelligence",
    "operations",
    "logistics",
    "plans",
    "signals",
    "training",
    "finance",
    "external",
)
STAFF_FOLDERS_MARKER_ROOT = f"{MODULE_ROOT}/.scaffolded/staff-folders"
_TEMPLATES_DIR = Path(__file__).resolve().parents[5] / "assets" / "staff_folders"


def _iso(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def _exists(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False


def build_manifest(workspace: WorkspaceModel) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "workspace": {
            "id": workspace.id,
            "name": workspace.name,
            "slug": workspace.slug,
            "organization_id": workspace.organization_id,
            "owner_id": workspace.owner_id,
            "created_at": _iso(workspace.created_at),
            "updated_at": _iso(workspace.updated_at),
        },
    }


def write_manifest(storage: ObjectStorageService, manifest: dict[str, Any]) -> None:
    storage.put_object(
        workspace_drive_root(manifest["workspace"]["id"]),
        MANIFEST_NAME,
        json.dumps(manifest, indent=2).encode("utf-8"),
    )


def has_manifest(storage: ObjectStorageService, workspace_id: str) -> bool:
    return _exists(storage, workspace_drive_root(workspace_id), MANIFEST_NAME)


def remove_legacy_manifest(storage: ObjectStorageService, workspace_id: str) -> bool:
    """Delete ``manifest.json`` if it is one this module wrote. Returns True if deleted.

    A ``manifest.json`` a user put at the drive root is left alone.
    """
    root = workspace_drive_root(workspace_id)
    try:
        content = storage.get_object(root, LEGACY_MANIFEST_NAME)
    except Exceptions.ObjectNotFound:
        return False
    try:
        data = json.loads(content)
        ours = (
            data.get("schema_version") == SCHEMA_VERSION
            and data.get("workspace", {}).get("id") == workspace_id
        )
    except (ValueError, AttributeError):
        ours = False
    if ours:
        storage.delete_object(root, LEGACY_MANIFEST_NAME)
    return ours


@cache
def staff_folder_readme(folder: str) -> str:
    """The folder's own text followed by the layout section shared by all nine."""
    body = (_TEMPLATES_DIR / f"{folder}.md").read_text(encoding="utf-8")
    layout = (_TEMPLATES_DIR / "_layout.md").read_text(encoding="utf-8")
    return body.rstrip("\n") + "\n" + layout


def has_staff_folders(storage: ObjectStorageService, workspace_id: str) -> bool:
    return _exists(storage, STAFF_FOLDERS_MARKER_ROOT, workspace_id)


def create_staff_folders(storage: ObjectStorageService, workspace_id: str) -> None:
    """Create the nine folders and their README, keeping anything already there."""
    root = workspace_drive_root(workspace_id)
    for folder in STAFF_FOLDERS:
        prefix = f"{root}/{folder}"
        if not _exists(storage, prefix, FilesService.folder_marker):
            storage.put_object(prefix, FilesService.folder_marker, b"")
        if not _exists(storage, prefix, README_NAME):
            storage.put_object(prefix, README_NAME, staff_folder_readme(folder).encode("utf-8"))
    storage.put_object(STAFF_FOLDERS_MARKER_ROOT, workspace_id, b"")


async def backfill_workspace_drives(
    session: AsyncSession, storage: ObjectStorageService
) -> dict[str, int]:
    """Write the missing manifests and staff folders, and drop legacy manifest.json files.

    Returns how many of each were written or removed.
    """
    workspaces = (await session.execute(select(WorkspaceModel))).scalars().all()
    manifests = [build_manifest(workspace) for workspace in workspaces]

    def _write_missing() -> dict[str, int]:
        written = {"manifests": 0, "staff_folders": 0, "legacy_manifests_removed": 0}
        for manifest in manifests:
            workspace_id = manifest["workspace"]["id"]
            try:
                if not has_manifest(storage, workspace_id):
                    write_manifest(storage, manifest)
                    written["manifests"] += 1
                if remove_legacy_manifest(storage, workspace_id):
                    written["legacy_manifests_removed"] += 1
                if not has_staff_folders(storage, workspace_id):
                    create_staff_folders(storage, workspace_id)
                    written["staff_folders"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[workspace-drive] backfill failed for {workspace_id}: {exc}")
        return written

    return await asyncio.to_thread(_write_missing)


class WorkspaceDriveWriter:
    """Install/uninstall the ORM listeners. One instance per object storage."""

    _key = "workspace_drives"

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
            created = [obj for obj in session.new if isinstance(obj, WorkspaceModel)]
            updated = [
                obj
                for obj in session.dirty
                if isinstance(obj, WorkspaceModel) and session.is_modified(obj)
            ]
            if not created and not updated:
                return
            # Keyed by id: the last flush of a transaction holds the committed values,
            # and a workspace created earlier in the transaction stays "created".
            staged = session.info.setdefault(self._key, {})
            for workspace in created:
                staged[workspace.id] = (build_manifest(workspace), True)
            for workspace in updated:
                was_created = staged.get(workspace.id, (None, False))[1]
                staged[workspace.id] = (build_manifest(workspace), was_created)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[workspace-drive] could not stage workspaces: {exc}")

    def _after_commit(self, session: Session) -> None:
        pending: dict[str, tuple[dict[str, Any], bool]] = session.info.pop(self._key, {})
        if not pending:
            return
        try:
            storage = self._get_storage()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[workspace-drive] object storage unavailable: {exc}")
            return
        for workspace_id, (manifest, created) in pending.items():
            try:
                write_manifest(storage, manifest)
                if created:
                    create_staff_folders(storage, workspace_id)
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[workspace-drive] write failed for {workspace_id}: {exc}")

    def _after_rollback(self, session: Session) -> None:
        session.info.pop(self._key, None)
