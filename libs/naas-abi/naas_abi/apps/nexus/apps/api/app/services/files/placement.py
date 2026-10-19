"""The object storage a workspace owns, placed in it (RFC §4.4).

A workspace owns one tree of the object storage: its drive,
``naas_abi/workspace-drive/<workspace_id>/``. IAM places that key (and everything
below it) in the workspace, so the workspace's roles reach it and nothing a
sibling workspace names can: a prefix placement ends at a ``/``, and the kernel
refuses ``.`` and ``..`` segments, so ``<ws>-2`` and ``<ws>/../<other>`` are
never inside ``<ws>``. Every other tree (the platform drive, the migration and
scaffolding markers, the analytics) belongs to the platform, and a user's own
drives are reached through the platform-level types of ``roles.PLATFORM_TYPES``.

Placed at startup for the workspaces that exist (``place_existing``), when a
workspace's drive is written (``place_workspace_drive_sync``) and, as a safety
net, the first time a request reaches the drive (``ensure_workspace_drive_placed``).
"""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import placements, runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.placements import (
    Placement,
    placement_source,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

SERVICE = "object_storage"

# Workspaces whose drive this process placed (or found placed).
_PLACED: set[str] = set()


def _segments(workspace_id: str) -> tuple[str, ...]:
    if not workspace_id or "/" in workspace_id or workspace_id in (".", ".."):
        raise ValueError(f"{workspace_id!r} is not a workspace id")
    return tuple(workspace_drive_root(workspace_id).split("/"))


def workspace_drive_placements(workspace_id: str) -> list[Placement]:
    """The drive's root folder, and everything below it."""
    parts = _segments(workspace_id)
    return [
        Placement(SERVICE, parts, workspace_id),
        Placement(SERVICE, parts, workspace_id, prefix=True),
    ]


@placement_source
async def workspace_drives(db: AsyncSession) -> Iterable[Placement]:
    rows = await db.execute(text("SELECT id FROM workspaces"))
    found: list[Placement] = []
    for (workspace_id,) in rows:
        try:
            found.extend(workspace_drive_placements(str(workspace_id)))
        except ValueError:
            logger.warning(f"Workspace {workspace_id!r} has no drive to place")
    return found


@placements.on_workspace_created
async def new_workspace_drive(db: AsyncSession, workspace_id: str) -> Iterable[Placement]:
    return workspace_drive_placements(workspace_id)


async def place_workspace_drive(workspace_id: str, *, org: str | None = None) -> None:
    await placements.place_many(workspace_drive_placements(workspace_id), org=org)
    _PLACED.add(workspace_id)


async def ensure_workspace_drive_placed(workspace_id: str) -> None:
    """Place the drive of a workspace the caller was just authorized in."""
    if workspace_id not in _PLACED:
        await place_workspace_drive(workspace_id)


def place_workspace_drive_sync(workspace_id: str) -> bool:
    """Place the drive from synchronous code (a commit hook). False when IAM does
    not know the workspace yet: the first request places it then."""
    iam = runtime.iam()
    with as_service_account("api"):
        org = iam.workspace_org(workspace_id)
        if org is None:
            return False
        for placement in workspace_drive_placements(workspace_id):
            iam.put_placement(placement.service, placement.id_key(), org, workspace_id)
    _PLACED.add(workspace_id)
    return True
