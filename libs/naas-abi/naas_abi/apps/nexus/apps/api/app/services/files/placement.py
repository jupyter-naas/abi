"""The object storage a workspace or an organization owns, placed in it.

A workspace owns one tree of the object storage: its Workspace Files,
``naas_abi/workspace-drive/<workspace_id>/``. IAM places that key (and everything
below it) in the workspace, so the workspace's roles reach it and nothing a
sibling workspace names can: a prefix placement ends at a ``/``, and the kernel
refuses ``.`` and ``..`` segments, so ``<ws>-2`` and ``<ws>/../<other>`` are
never inside ``<ws>``. An organization owns its Organization Files the same way,
``naas_abi/organization-drive/<organization_id>/``, placed in the organization's
own container: the roles held at the organization reach it, a role held only in
one of its workspaces does not. Every other tree (Platform Files, the migration and
scaffolding markers, the analytics) belongs to the platform, and a user's My Files
and storage are reached through the rows of the roles' platform companions: the
kernel's (``roles.PLATFORM_TYPES``) and the ``nexus`` catalog's ``PLATFORM_ACCESS``.

Placed at startup for the workspaces and organizations that exist
(``place_existing``), when a drive is written (``place_workspace_drive_sync``,
``place_organization_drive_sync``) and, as a safety net, the first time a request
reaches the drive (``ensure_workspace_drive_placed``,
``ensure_organization_drive_placed``).
"""

from __future__ import annotations

from collections.abc import Iterable

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    organization_drive_root,
    workspace_drive_root,
)
from naas_abi.apps.nexus.apps.api.app.services.iam import placements, runtime
from naas_abi.apps.nexus.apps.api.app.services.iam.names import ORGANIZATION, WORKSPACE
from naas_abi.apps.nexus.apps.api.app.services.iam.names import SERVICE as NEXUS
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
# Organizations whose drive this process placed (or found placed).
_PLACED_ORGS: set[str] = set()


def _check_id(value: str, what: str) -> None:
    if not value or "/" in value or value in (".", ".."):
        raise ValueError(f"{value!r} is not a {what} id")


def _segments(workspace_id: str) -> tuple[str, ...]:
    _check_id(workspace_id, "workspace")
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
        container = iam.container(NEXUS, WORKSPACE, workspace_id)
        if container is None:
            return False
        for placement in workspace_drive_placements(workspace_id):
            iam.put_placement(placement.service, placement.id_key(), container)
    _PLACED.add(workspace_id)
    return True


# -- Organization Files --------------------------------------------------------


def organization_drive_placements(organization_id: str) -> list[Placement]:
    """Organization Files' root folder, and everything below it, in the
    organization's own container."""
    _check_id(organization_id, "organization")
    parts = tuple(organization_drive_root(organization_id).split("/"))
    return [
        Placement(SERVICE, parts, "", organization=organization_id),
        Placement(SERVICE, parts, "", prefix=True, organization=organization_id),
    ]


@placement_source
async def organization_drives(db: AsyncSession) -> Iterable[Placement]:
    rows = await db.execute(text("SELECT id FROM organizations"))
    found: list[Placement] = []
    for (organization_id,) in rows:
        try:
            found.extend(organization_drive_placements(str(organization_id)))
        except ValueError:
            logger.warning(f"Organization {organization_id!r} has no drive to place")
    return found


async def ensure_organization_drive_placed(organization_id: str) -> None:
    """Place the drive of an organization the caller was just authorized in."""
    if organization_id not in _PLACED_ORGS:
        await placements.place_many(organization_drive_placements(organization_id))
        _PLACED_ORGS.add(organization_id)


def place_organization_drive_sync(organization_id: str) -> bool:
    """Place the drive from synchronous code (a commit hook). False when IAM does
    not know the organization yet: the first request places it then."""
    iam = runtime.iam()
    with as_service_account("api"):
        container = iam.container(NEXUS, ORGANIZATION, organization_id)
        if container is None:
            return False
        for placement in organization_drive_placements(organization_id):
            iam.put_placement(placement.service, placement.id_key(), container)
    _PLACED_ORGS.add(organization_id)
    return True
