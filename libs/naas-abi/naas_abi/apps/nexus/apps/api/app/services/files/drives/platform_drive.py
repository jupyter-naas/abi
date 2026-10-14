"""Set up the platform drive's staff system folders.

``naas_abi/platform-drive/`` gets the same nine folders as a workspace drive
(``personnel/``, ``intelligence/``, ... ``external/``), each with its
``README.md``. They are created once, on API boot. A marker under
``naas_abi/.scaffolded/platform-drive/`` records it, so a folder someone
deletes is not brought back, and a README already stored there is left as it is.
"""

from __future__ import annotations

import asyncio

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    MODULE_ROOT,
    platform_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.objects import object_exists
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.staff_folders import (
    write_staff_folders,
)
from naas_abi_core import logger
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

PLATFORM_STAFF_MARKER_ROOT = f"{MODULE_ROOT}/.scaffolded/platform-drive"
PLATFORM_STAFF_MARKER = "staff-folders"


def has_platform_staff_folders(storage: ObjectStorageService) -> bool:
    return object_exists(storage, PLATFORM_STAFF_MARKER_ROOT, PLATFORM_STAFF_MARKER)


def create_platform_staff_folders(storage: ObjectStorageService) -> None:
    """Create the nine staff folders on the platform drive, keeping anything already there."""
    write_staff_folders(storage, platform_drive_root())
    storage.put_object(PLATFORM_STAFF_MARKER_ROOT, PLATFORM_STAFF_MARKER, b"")


def ensure_platform_staff_folders(storage: ObjectStorageService) -> bool:
    """Write the platform drive's staff folders if they were never created.

    Returns True when this call created them.
    """
    if has_platform_staff_folders(storage):
        return False
    create_platform_staff_folders(storage)
    return True


async def backfill_platform_drive(storage: ObjectStorageService) -> dict[str, int]:
    """Create the platform drive's staff folders the first time this runs."""

    def _write() -> dict[str, int]:
        try:
            created = ensure_platform_staff_folders(storage)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[platform-drive] staff folders failed: {exc}")
            return {"staff_folders": 0}
        return {"staff_folders": int(created)}

    return await asyncio.to_thread(_write)
