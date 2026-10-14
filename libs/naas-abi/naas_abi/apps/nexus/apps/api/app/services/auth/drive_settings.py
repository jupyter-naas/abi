"""A user's settings files in their own drive, with archived previous versions.

``naas_abi/my-drive/<user_id>/.settings/<section>/`` holds the current file(s);
``.settings/<section>/archives/<ts>_<name>`` keeps every previous version, so
replacing or removing a settings file never loses the old one. Used by
``avatar_store`` (pictures) and ``user_settings_store`` (``user.json``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    my_drive_root,
)
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions as StorageExceptions,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

ARCHIVES_DIR = "archives"


def settings_prefix(user_id: str, section: str) -> str:
    return f"{my_drive_root(user_id)}/.settings/{section}"


def archives_prefix(user_id: str, section: str) -> str:
    return f"{settings_prefix(user_id, section)}/{ARCHIVES_DIR}"


def timestamp(now: datetime) -> str:
    return now.strftime("%Y%m%dT%H%M%SZ")


def archive(
    storage: ObjectStorageService,
    user_id: str,
    section: str,
    key: str,
    content: bytes,
    now: datetime,
) -> str:
    """Copy ``content`` (the current ``key``) to ``archives/<ts>_<key>``; returns that key."""
    archived_key = f"{timestamp(now)}_{key}"
    storage.put_object(archives_prefix(user_id, section), archived_key, content)
    return archived_key


@dataclass
class VersionedSaveResult:
    #: False when the stored file already held exactly this content.
    changed: bool
    archived_key: str | None = None


def encode_json(document: dict[str, Any]) -> bytes:
    """Stable JSON (sorted keys), so an unchanged document gives the same bytes."""
    return (json.dumps(document, indent=2, sort_keys=True, ensure_ascii=False) + "\n").encode()


def save_versioned(
    storage: ObjectStorageService,
    user_id: str,
    section: str,
    key: str,
    content: bytes,
    now: datetime,
) -> VersionedSaveResult:
    """Write ``.settings/<section>/<key>`` if it changed, archiving the previous version."""
    prefix = settings_prefix(user_id, section)
    try:
        current = storage.get_object(prefix, key)
    except StorageExceptions.ObjectNotFound:
        current = None
    if current == content:
        return VersionedSaveResult(changed=False)
    archived_key = (
        archive(storage, user_id, section, key, current, now) if current is not None else None
    )
    storage.put_object(prefix, key, content)
    return VersionedSaveResult(changed=True, archived_key=archived_key)
