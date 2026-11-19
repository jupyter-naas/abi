"""Set up every organization's drive: ``.manifest.json`` and the staff system folders.

``naas_abi/organization-drive/<organization_id>/`` is where files that belong to
the organization as a whole live (policies, contracts, brand assets, onboarding
packs), seen from every workspace of the organization. It gets:

- ``.manifest.json``, describing the organization the folder belongs to, so the
  drive can be identified from object storage alone. It is rewritten whenever
  the organization is updated.
- the nine staff system folders (``personnel/``, ``intelligence/``, ...
  ``external/``), each with its ``README.md``, as the workspace and platform
  drives have. They are created once per organization; a marker under
  ``naas_abi/.scaffolded/organization-drive/`` records it, so a folder someone
  deletes is not brought back.

Organizations are created by the organizations API and by the configuration
seeds at boot. Like ``WorkspaceDriveWriter``, this listens to SQLAlchemy ORM
sessions rather than instrumenting each path: ``after_flush`` stages created or
updated ``OrganizationModel`` rows, ``after_commit`` writes them (and places a new
drive in the organization's container), ``after_rollback`` drops them.

``backfill_organization_drives`` does the same at start for organizations created
before this existed. Writing to the drive must never break a commit: a storage
failure is logged.

Who reaches the drive is IAM's, at the organization's container
(``nexus:ListOrgFiles``, ``GetOrgFile``, ``PutOrgFile``, ``DeleteOrgFile``).
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Callable
from typing import Any

from naas_abi.apps.nexus.apps.api.app.models import OrganizationModel
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    MODULE_ROOT,
    organization_drive_root,
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
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.staff_folders import (
    write_staff_folders,
)
from naas_abi.apps.nexus.apps.api.app.services.files.placement import (
    place_organization_drive_sync,
)
from naas_abi_core import logger
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService
from sqlalchemy import event as sa_event
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

ORGANIZATION_STAFF_MARKER_ROOT = f"{MODULE_ROOT}/.scaffolded/organization-drive"


def build_manifest(organization: OrganizationModel) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "organization": {
            "id": organization.id,
            "name": organization.name,
            "slug": organization.slug,
            "owner_id": organization.owner_id,
            "created_at": _iso(organization.created_at),
            "updated_at": _iso(organization.updated_at),
        },
    }


def write_manifest(storage: ObjectStorageService, manifest: dict[str, Any]) -> None:
    storage.put_object(
        organization_drive_root(manifest["organization"]["id"]),
        MANIFEST_NAME,
        json.dumps(manifest, indent=2).encode("utf-8"),
    )


def has_manifest(storage: ObjectStorageService, organization_id: str) -> bool:
    return _exists(storage, organization_drive_root(organization_id), MANIFEST_NAME)


def has_staff_folders(storage: ObjectStorageService, organization_id: str) -> bool:
    return _exists(storage, ORGANIZATION_STAFF_MARKER_ROOT, organization_id)


def create_staff_folders(storage: ObjectStorageService, organization_id: str) -> None:
    """Create the nine folders and their README, keeping anything already there."""
    write_staff_folders(storage, organization_drive_root(organization_id))
    storage.put_object(ORGANIZATION_STAFF_MARKER_ROOT, organization_id, b"")


async def backfill_organization_drives(
    session: AsyncSession, storage: ObjectStorageService
) -> dict[str, int]:
    """Write the missing manifests and staff folders. Returns how many of each."""
    organizations = (await session.execute(select(OrganizationModel))).scalars().all()
    manifests = [build_manifest(organization) for organization in organizations]

    def _write_missing() -> dict[str, int]:
        written = {"manifests": 0, "staff_folders": 0}
        for manifest in manifests:
            organization_id = manifest["organization"]["id"]
            try:
                if not has_manifest(storage, organization_id):
                    write_manifest(storage, manifest)
                    written["manifests"] += 1
                if not has_staff_folders(storage, organization_id):
                    create_staff_folders(storage, organization_id)
                    written["staff_folders"] += 1
            except Exception as exc:  # noqa: BLE001
                logger.warning(f"[organization-drive] backfill failed for {organization_id}: {exc}")
        return written

    return await asyncio.to_thread(_write_missing)


def _place(organization_id: str) -> None:
    """Place a new organization's drive. Without IAM, or before IAM knows the
    organization, the first request that reaches the drive places it."""
    try:
        place_organization_drive_sync(organization_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"[organization-drive] placement deferred for {organization_id}: {exc}")


class OrganizationDriveWriter:
    """Install/uninstall the ORM listeners. One instance per object storage."""

    _key = "organization_drives"

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
            created = [obj for obj in session.new if isinstance(obj, OrganizationModel)]
            updated = [
                obj
                for obj in session.dirty
                if isinstance(obj, OrganizationModel) and session.is_modified(obj)
            ]
            if not created and not updated:
                return
            # Keyed by id: the last flush of a transaction holds the committed values,
            # and an organization created earlier in the transaction stays "created".
            staged = session.info.setdefault(self._key, {})
            for organization in created:
                staged[organization.id] = (build_manifest(organization), True)
            for organization in updated:
                was_created = staged.get(organization.id, (None, False))[1]
                staged[organization.id] = (build_manifest(organization), was_created)
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[organization-drive] could not stage organizations: {exc}")

    def _after_commit(self, session: Session) -> None:
        pending: dict[str, tuple[dict[str, Any], bool]] = session.info.pop(self._key, {})
        if not pending:
            return
        try:
            storage = self._get_storage()
        except Exception as exc:  # noqa: BLE001
            logger.warning(f"[organization-drive] object storage unavailable: {exc}")
            return
        # The drive is Nexus's own scaffolding, written for no caller: the committing
        # request's user may not hold the drive yet (a new organization's owner).
        with as_service_account("api"):
            for organization_id, (manifest, created) in pending.items():
                if created:
                    _place(organization_id)
                try:
                    write_manifest(storage, manifest)
                    if created:
                        create_staff_folders(storage, organization_id)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        f"[organization-drive] write failed for {organization_id}: {exc}"
                    )

    def _after_rollback(self, session: Session) -> None:
        session.info.pop(self._key, None)
