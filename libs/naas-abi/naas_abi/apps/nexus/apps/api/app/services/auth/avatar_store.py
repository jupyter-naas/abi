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

import hashlib
import os
from dataclasses import dataclass
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.services.auth import drive_settings
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions as StorageExceptions,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

AVATAR_EXTENSIONS = (".png", ".jpg", ".jpeg", ".gif", ".webp")
AVATAR_BASENAME = "avatar"
ORG_AVATAR_BASENAME = "avatar_org"
SECTION = "avatar"


def avatar_prefix(user_id: str) -> str:
    return drive_settings.settings_prefix(user_id, SECTION)


def archive_prefix(user_id: str) -> str:
    return drive_settings.archives_prefix(user_id, SECTION)


def avatar_url(user_id: str, digest: str, basename: str = AVATAR_BASENAME) -> str:
    """URL stored on the user (or member); the digest changes with the picture, so caches refresh."""
    suffix = "/org" if basename == ORG_AVATAR_BASENAME else ""
    return f"/api/auth/avatar/user/{user_id}{suffix}?v={digest[:12]}"


def _digest(content: bytes) -> str:
    return hashlib.sha256(content).hexdigest()


@dataclass
class StoredAvatar:
    key: str
    content: bytes

    @property
    def extension(self) -> str:
        return os.path.splitext(self.key)[1]


@dataclass
class AvatarSaveResult:
    key: str
    digest: str
    #: False when the upload matched the current picture byte for byte.
    changed: bool
    archived_key: str | None = None


def read_avatar(
    storage: ObjectStorageService, user_id: str, basename: str = AVATAR_BASENAME
) -> StoredAvatar | None:
    """The current picture, whatever its extension, or None."""
    prefix = avatar_prefix(user_id)
    for extension in AVATAR_EXTENSIONS:
        key = f"{basename}{extension}"
        try:
            return StoredAvatar(key=key, content=storage.get_object(prefix, key))
        except StorageExceptions.ObjectNotFound:
            continue
    return None


def _archive(
    storage: ObjectStorageService, user_id: str, current: StoredAvatar, now: datetime
) -> str:
    return drive_settings.archive(storage, user_id, SECTION, current.key, current.content, now)


def save_avatar(
    storage: ObjectStorageService,
    user_id: str,
    content: bytes,
    extension: str,
    now: datetime,
    basename: str = AVATAR_BASENAME,
) -> AvatarSaveResult:
    """Store ``content`` as the current picture, archiving the previous one if it differs."""
    extension = extension.lower()
    if extension not in AVATAR_EXTENSIONS:
        raise ValueError(f"Unsupported avatar extension: {extension}")
    digest = _digest(content)
    current = read_avatar(storage, user_id, basename)
    if current is not None and _digest(current.content) == digest:
        return AvatarSaveResult(key=current.key, digest=digest, changed=False)

    archived_key = _archive(storage, user_id, current, now) if current is not None else None
    key = f"{basename}{extension}"
    storage.put_object(avatar_prefix(user_id), key, content)
    if current is not None and current.key != key:
        # Different extension: drop the old file, or read_avatar could still find it first.
        storage.delete_object(avatar_prefix(user_id), current.key)
    return AvatarSaveResult(key=key, digest=digest, changed=True, archived_key=archived_key)


def remove_avatar(
    storage: ObjectStorageService,
    user_id: str,
    now: datetime,
    basename: str = AVATAR_BASENAME,
) -> str | None:
    """Archive and remove the current picture; returns the archived key, or None if none."""
    current = read_avatar(storage, user_id, basename)
    if current is None:
        return None
    archived_key = _archive(storage, user_id, current, now)
    storage.delete_object(avatar_prefix(user_id), current.key)
    return archived_key
