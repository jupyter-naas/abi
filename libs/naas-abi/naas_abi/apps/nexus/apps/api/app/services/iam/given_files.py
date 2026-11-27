"""The files a workspace gives its people outside it: the Files part of its offer (ADR
``20261125_offer_gives_outside_resources``).

"<W> access" may hold Allow statements naming resources outside W, absolute names and
no ``${scope}``: IAM reads them as grants to the people of W (the members of its
membership groups) while they belong to W, each action within their level there (core
"Given statements"). Three of them are files, each a mode:

| Section | Modes | Statements |
|---|---|---|
| ``GivenOrgFiles`` | off, read, write | ``nexus:*OrgFile*`` on ``<O>/nexus:file/organization`` and below; ``GivenOrgFiles2``: ``object_storage`` on ``<O>/object_storage:object/naas_abi/organization-drive/<o>`` and below |
| ``GivenPlatformFiles`` | off, read, write | ``nexus:*PlatformFile*`` on ``abi:nexus:platform_file/*``; ``GivenPlatformFiles2``: ``object_storage`` on ``abi:object_storage:object/naas_abi/platform-drive`` and below |
| ``GivenSystemFiles`` | off, read | ``nexus:ListObjectStoreFiles``, ``GetObjectStoreFile`` on ``abi:nexus:system_file/*``; ``GivenSystemFiles2``: ``object_storage`` read on every key, at the platform and in every container |

Each names both halves: the files routes decide on the ``nexus`` actions, and the object
storage, called as the person, decides again on its own keys. Read lists and reads;
write also creates, changes and deletes. Organization Files are the workspace's own
organization's: a workspace in none has no such section.

Workspace Files is the ``files`` feature (``OfferFeatures``). My Files is not in the
offer: a deployment setting of the Viewer level (``feature_flags.viewer_my_files``,
``levels``).

Pure: no IAM, no database.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any, Literal

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    PLATFORM,
    nexus_resource,
    org_container,
    org_of,
)
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.object_storage.iam_catalog import object_parts

Mode = Literal["off", "read", "write"]
OFF: Mode = "off"
READ: Mode = "read"
WRITE: Mode = "write"
# Narrower first.
ORDER: tuple[Mode, ...] = (OFF, READ, WRITE)

ORG_FILES = "org_files"
PLATFORM_FILES = "platform_files"
SYSTEM_FILES = "system_files"

ORG_FILES_SID = "GivenOrgFiles"
PLATFORM_FILES_SID = "GivenPlatformFiles"
SYSTEM_FILES_SID = "GivenSystemFiles"
# The ``Offer`` field each section fills, by sid.
SIDS: dict[str, str] = {
    ORG_FILES: ORG_FILES_SID,
    PLATFORM_FILES: PLATFORM_FILES_SID,
    SYSTEM_FILES: SYSTEM_FILES_SID,
}
FIELD_OF_SID = {sid: field for field, sid in SIDS.items()}
# What each section may be.
MODES: dict[str, tuple[Mode, ...]] = {
    ORG_FILES: (OFF, READ, WRITE),
    PLATFORM_FILES: (OFF, READ, WRITE),
    SYSTEM_FILES: (OFF, READ),
}
LABELS: dict[str, str] = {
    ORG_FILES: "Organization Files",
    PLATFORM_FILES: "Platform Files",
    SYSTEM_FILES: "System Files",
}

PLATFORM_DRIVE = "naas_abi/platform-drive"
ORGANIZATION_DRIVE = "naas_abi/organization-drive"

OBJECT_READ_ACTIONS: tuple[str, ...] = (
    "object_storage:ListObjects",
    "object_storage:ListObjectsRecursive",
    "object_storage:GetObject",
    "object_storage:GetObjectMetadata",
    "object_storage:GetObjectStream",
)
OBJECT_WRITE_ACTIONS: tuple[str, ...] = (
    "object_storage:PutObject",
    "object_storage:PutObjectStream",
    "object_storage:DeleteObject",
)
# Each section's Nexus actions, read and write.
NEXUS_ACTIONS: dict[str, tuple[tuple[str, ...], tuple[str, ...]]] = {
    ORG_FILES: (
        ("nexus:ListOrgFiles", "nexus:GetOrgFile"),
        ("nexus:PutOrgFile", "nexus:DeleteOrgFile"),
    ),
    PLATFORM_FILES: (
        ("nexus:ListPlatformFiles", "nexus:GetPlatformFile"),
        ("nexus:PutPlatformFile", "nexus:DeletePlatformFile"),
    ),
    SYSTEM_FILES: (("nexus:ListObjectStoreFiles", "nexus:GetObjectStoreFile"), ()),
}


def wider(a: Mode | None, b: Mode | None) -> Mode | None:
    """The wider of two modes (None and ``off`` give nothing)."""
    found = max(ORDER.index(a or OFF), ORDER.index(b or OFF))
    return ORDER[found] if found else None


def narrower_or_equal(a: Mode | None, b: Mode | None) -> bool:
    return ORDER.index(a or OFF) <= ORDER.index(b or OFF)


# -- the resources ---------------------------------------------------------------------


def _below(name: str) -> list[str]:
    return [name, name + "/*"]


def platform_file_resources() -> list[str]:
    """Every Platform File, ``abi:nexus:platform_file/*``."""
    root = nexus_resource("platform_file", id=("platform",))
    return [root.rsplit("/", 1)[0] + "/*"]


def platform_drive_objects() -> list[str]:
    """The platform drive's folder and every object below it, in the object storage."""
    return _below(
        resource_name("object_storage", "object", object_parts(PLATFORM_DRIVE), kind="path")
    )


def org_file_resources(organization_id: str) -> list[str]:
    """The organization's Organization Files: ``<O>/nexus:file/organization`` and below,
    what the files routes decide on."""
    return _below(
        nexus_resource("file", container=org_container(organization_id), id=("organization",))
    )


def org_drive_objects(organization_id: str) -> list[str]:
    """The organization's drive in the object storage, placed in its container."""
    folder = f"{ORGANIZATION_DRIVE}/{organization_id}"
    return _below(
        resource_name(
            "object_storage",
            "object",
            object_parts(folder),
            kind="path",
            container=org_container(organization_id),
        )
    )


def system_file_resources() -> list[str]:
    """Every System File, ``abi:nexus:system_file/*``."""
    root = nexus_resource("system_file", id=("system",))
    return [root.rsplit("/", 1)[0] + "/*"]


def every_object() -> list[str]:
    """Every key of the object storage: at the platform, and placed in any container
    (a workspace's drive, an organization's)."""
    any_key = resource_name("object_storage", "object", ("-",), kind="path").rsplit("/", 1)[0]
    return [f"{any_key}/*", f"{PLATFORM}*/{any_key.removeprefix(PLATFORM)}/*"]


# -- the statements --------------------------------------------------------------------


def _statement(sid: str, actions: Iterable[str], resources: list[str]) -> dict[str, Any]:
    return {"sid": sid, "effect": "Allow", "actions": list(actions), "resources": resources}


def statements(field: str, mode: Mode | None, organization: str | None = None) -> list[dict]:
    """The section ``field`` (``org_files``, ``platform_files``, ``system_files``) in
    ``mode``: its Nexus half, then its object storage half (``<sid>2``). None and
    ``off``: no statement. ``organization`` names the organization for
    ``org_files``."""
    if mode in (None, OFF):
        return []
    if mode not in MODES[field]:
        raise ValueError(f"{LABELS[field]} is one of {', '.join(MODES[field])}, not {mode!r}")
    sid = SIDS[field]
    reads, writes = NEXUS_ACTIONS[field]
    nexus = [*reads, *(writes if mode == WRITE else ())]
    objects = [*OBJECT_READ_ACTIONS, *(OBJECT_WRITE_ACTIONS if mode == WRITE else ())]
    if field == ORG_FILES:
        if not organization:
            raise ValueError("Organization Files: name the organization")
        files, keys = org_file_resources(organization), org_drive_objects(organization)
    elif field == PLATFORM_FILES:
        files, keys = platform_file_resources(), platform_drive_objects()
    else:
        files, keys = system_file_resources(), every_object()
    return [_statement(sid, nexus, files), _statement(f"{sid}2", objects, keys)]


def mode_of(field: str, actions: Iterable[str]) -> Mode | None:
    """The mode a section's actions say: write when it writes files, read when it lists
    them, else None."""
    found = set(actions)
    reads, writes = NEXUS_ACTIONS[field]
    if writes and set(writes) <= found:
        return WRITE
    if set(reads) <= found:
        return READ
    return None


def organization_of(resources: Iterable[str]) -> str | None:
    """The organization a ``GivenOrgFiles`` statement names."""
    for resource in resources:
        found = org_of(resource)
        if found:
            return found
    return None


__all__ = [
    "FIELD_OF_SID",
    "LABELS",
    "MODES",
    "OFF",
    "ORG_FILES",
    "PLATFORM_FILES",
    "READ",
    "SIDS",
    "SYSTEM_FILES",
    "WRITE",
    "Mode",
    "every_object",
    "mode_of",
    "narrower_or_equal",
    "org_drive_objects",
    "org_file_resources",
    "organization_of",
    "platform_drive_objects",
    "platform_file_resources",
    "statements",
    "system_file_resources",
    "wider",
]
