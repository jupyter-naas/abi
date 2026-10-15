"""Workspace logos in the workspace's own drive (same logic as account avatars).

``naas_abi/workspace-drive/<workspace_id>/.settings/logos/``:

    logo.<ext>                    the current logo
    archives/<ts>_logo.<ext>      previous logos

An upload identical to the current logo (same SHA-256) changes nothing;
otherwise the previous logo is archived first (``versioned_files``).
"""

from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils import versioned_files
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    workspace_drive_root,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

LOGO_BASENAME = "logo"
LOGO_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def logo_prefix(workspace_id: str) -> str:
    return f"{workspace_drive_root(workspace_id)}/.settings/logos"


def logo_url(workspace_id: str, digest: str) -> str:
    """URL stored on the workspace; the digest changes with the logo, so caches refresh."""
    return f"/api/workspaces/{workspace_id}/logo?v={digest[:12]}"


def read_logo(
    storage: ObjectStorageService, workspace_id: str
) -> versioned_files.StoredImage | None:
    return versioned_files.read_image(
        storage, logo_prefix(workspace_id), LOGO_BASENAME, LOGO_EXTENSIONS
    )


def save_logo(
    storage: ObjectStorageService,
    workspace_id: str,
    content: bytes,
    extension: str,
    now: datetime,
) -> versioned_files.ImageSaveResult:
    return versioned_files.save_image(
        storage, logo_prefix(workspace_id), LOGO_BASENAME, content, extension, now, LOGO_EXTENSIONS
    )


def remove_logo(storage: ObjectStorageService, workspace_id: str, now: datetime) -> str | None:
    return versioned_files.remove_image(
        storage, logo_prefix(workspace_id), LOGO_BASENAME, now, LOGO_EXTENSIONS
    )
