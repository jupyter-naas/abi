"""Storage layout constants for the naas_abi module.

All user-facing object storage paths live under a single module root so the
drive scopes (my-drive, workspace-drive, organization-drive, platform-drive) sit
side by side in the datastore:

    naas_abi/
        my-drive/<user_id>/...
        workspace-drive/<workspace_id>/...
        organization-drive/<organization_id>/...
        platform-drive/...

Each is the root of a view of the file system, opened by IAM alone (``GET
/api/files/views``): Organization Files belongs to its organization (IAM decides
at the organization's container, ``nexus:ListOrgFiles`` and the others, and a
workspace reaches only its own organization's). Platform Files is one tree
shared by the platform: nobody's until a policy at the platform grants
``nexus:*PlatformFile*``. System Files is the whole store, the platform admin's.
"""

from __future__ import annotations

import re
from pathlib import PurePosixPath

MODULE_ROOT = "naas_abi"
MY_DRIVE_ROOT = f"{MODULE_ROOT}/my-drive"
WORKSPACE_DRIVE_ROOT = f"{MODULE_ROOT}/workspace-drive"
ORGANIZATION_DRIVE_ROOT = f"{MODULE_ROOT}/organization-drive"
PLATFORM_DRIVE_ROOT = f"{MODULE_ROOT}/platform-drive"
# System Files exposes the full object-storage tree — not just
# the ``naas_abi`` module root, but everything stored alongside it. The platform
# admin's, to inspect and manage object storage across all users and workspaces.
# An empty root means "no prefix": paths are resolved directly against the
# underlying object storage.
SYSTEM_DRIVE_ROOT = ""

SCOPE_WORKSPACE = "workspace"
SCOPE_MY_DRIVE = "my_drive"
SCOPE_ORGANIZATION_DRIVE = "organization_drive"
SCOPE_PLATFORM_DRIVE = "platform_drive"
SCOPE_SYSTEM_DRIVE = "system_drive"
SCOPE_PATTERN = r"^(workspace|my_drive|organization_drive|platform_drive|system_drive)$"


def my_drive_root(user_id: str) -> str:
    return PurePosixPath(MY_DRIVE_ROOT, user_id).as_posix()


def workspace_drive_root(workspace_id: str) -> str:
    return PurePosixPath(WORKSPACE_DRIVE_ROOT, workspace_id).as_posix()


def organization_drive_root(organization_id: str) -> str:
    return PurePosixPath(ORGANIZATION_DRIVE_ROOT, organization_id).as_posix()


def platform_drive_root() -> str:
    return PLATFORM_DRIVE_ROOT


def system_drive_root() -> str:
    return SYSTEM_DRIVE_ROOT


_SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,127}$")


def is_safe_drive_id(value: str) -> bool:
    """True for a plain user, workspace or organization id, safe to build a drive path from.

    Public routes (pictures, logos) take the id from the URL: anything else
    (``..``, dots, separators) could escape the drive on a filesystem backend.
    """
    return bool(_SAFE_ID.match(value))
