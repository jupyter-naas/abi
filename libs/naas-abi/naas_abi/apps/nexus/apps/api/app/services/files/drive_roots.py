"""Storage layout constants for the naas_abi module.

All user-facing object storage paths live under a single module root so the
three drive scopes (my-drive, workspace-drive, platform-drive) sit side by side
in the datastore:

    naas_abi/
        my-drive/<user_id>/...
        workspace-drive/<workspace_id>/...
        platform-drive/...

The platform drive is a single tree shared across every workspace; access is
gated per-workspace via the ``platform_drive_enabled`` flag on the workspace
row.
"""

from __future__ import annotations

from pathlib import PurePosixPath

MODULE_ROOT = "naas_abi"
MY_DRIVE_ROOT = f"{MODULE_ROOT}/my-drive"
WORKSPACE_DRIVE_ROOT = f"{MODULE_ROOT}/workspace-drive"
PLATFORM_DRIVE_ROOT = f"{MODULE_ROOT}/platform-drive"
# The system drive exposes the full object-storage tree — not just the
# ``naas_abi`` module root, but everything stored alongside it. Reserved for
# workspace admins/owners to inspect and manage object storage across all
# users and workspaces. An empty root means "no prefix": paths are resolved
# directly against the underlying object storage.
SYSTEM_DRIVE_ROOT = ""

SCOPE_WORKSPACE = "workspace"
SCOPE_MY_DRIVE = "my_drive"
SCOPE_PLATFORM_DRIVE = "platform_drive"
SCOPE_SYSTEM_DRIVE = "system_drive"
SCOPE_PATTERN = r"^(workspace|my_drive|platform_drive|system_drive)$"


def my_drive_root(user_id: str) -> str:
    return PurePosixPath(MY_DRIVE_ROOT, user_id).as_posix()


def my_drive_code_root(user_id: str) -> str:
    """Per-user Code IDE sandbox inside My Drive."""
    return PurePosixPath(MY_DRIVE_ROOT, user_id, "code").as_posix()


def workspace_drive_root(workspace_id: str) -> str:
    return PurePosixPath(WORKSPACE_DRIVE_ROOT, workspace_id).as_posix()


def platform_drive_root() -> str:
    return PLATFORM_DRIVE_ROOT


def system_drive_root() -> str:
    return SYSTEM_DRIVE_ROOT
