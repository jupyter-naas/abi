"""Account avatars in the user's own drive (see ``drive_settings``).

Layout (``naas_abi/my-drive/<user_id>/`` is the personal drive, see
``files.drives.utils.drive_roots``)::

    .settings/avatar/avatar.<ext>                      the account picture
    .settings/avatar/avatar_org.<ext>                  the organization member picture
    .settings/avatar/archives/<ts>_<name>.<ext>        previous pictures

The organization picture is set by org admins (Organization Settings > Users);
the account shows it when the account has no picture of its own.

An upload whose bytes match the current picture (same SHA-256) changes nothing.
Otherwise the current picture is copied to ``archives/`` first, so replacing or
removing a picture never loses the old one.
"""

from __future__ import annotations

from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.auth import drive_settings
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils import versioned_files
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

AVATAR_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
AVATAR_BASENAME = "avatar"
ORG_AVATAR_BASENAME = "avatar_org"
SECTION = "avatar"

StoredAvatar = versioned_files.StoredImage
AvatarSaveResult = versioned_files.ImageSaveResult


def avatar_prefix(user_id: str) -> str:
    return drive_settings.settings_prefix(user_id, SECTION)


def avatar_url(user_id: str, digest: str, basename: str = AVATAR_BASENAME) -> str:
    """URL stored on the user (or member); the digest changes with the picture, so caches refresh."""
    suffix = "/org" if basename == ORG_AVATAR_BASENAME else ""
    return f"/api/auth/avatar/user/{user_id}{suffix}?v={digest[:12]}"


def read_avatar(
    storage: ObjectStorageService, user_id: str, basename: str = AVATAR_BASENAME
) -> StoredAvatar | None:
    """The current picture, whatever its extension, or None."""
    return versioned_files.read_image(storage, avatar_prefix(user_id), basename, AVATAR_EXTENSIONS)


def save_avatar(
    storage: ObjectStorageService,
    user_id: str,
    content: bytes,
    extension: str,
    now: datetime,
    basename: str = AVATAR_BASENAME,
) -> AvatarSaveResult:
    """Store ``content`` as the current picture, archiving the previous one if it differs."""
    return versioned_files.save_image(
        storage, avatar_prefix(user_id), basename, content, extension, now, AVATAR_EXTENSIONS
    )


def remove_avatar(
    storage: ObjectStorageService,
    user_id: str,
    now: datetime,
    basename: str = AVATAR_BASENAME,
) -> str | None:
    """Archive and remove the current picture; returns the archived key, or None if none."""
    return versioned_files.remove_image(
        storage, avatar_prefix(user_id), basename, now, AVATAR_EXTENSIONS
    )
