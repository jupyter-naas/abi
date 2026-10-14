"""The user's account info as ``.settings/user/user.json`` in their own drive.

Same archive logic as the avatar (see ``drive_settings``): the file is rewritten
only when its content changes, and the previous version is first copied to
``.settings/user/archives/<ts>_user.json``. The password hash is never written.

The database stays the source of truth; this file is a readable copy the user
owns, refreshed whenever their profile or picture changes.
"""

from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any, Protocol

from naas_abi.apps.nexus.apps.api.app.services.auth import drive_settings
from naas_abi_core.services.object_storage.ObjectStoragePort import (
    Exceptions as StorageExceptions,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

SECTION = "user"
USER_SETTINGS_KEY = "user.json"
SCHEMA_VERSION = 1


class UserInfo(Protocol):
    """Fields shared by the auth record and the API ``User`` schema."""

    id: str
    email: str
    name: str
    organization: str | None
    job_title: str | None
    bio: str | None
    avatar: str | None
    is_superadmin: bool
    created_at: datetime


UserSettingsSaveResult = drive_settings.VersionedSaveResult


def _iso(value: Any) -> Any:
    return value.isoformat() if isinstance(value, datetime | date) else value


def user_settings_document(user: UserInfo) -> dict[str, Any]:
    """What ``user.json`` holds; no timestamp that changes on every save."""
    return {
        "schema_version": SCHEMA_VERSION,
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "organization": user.organization,
            "job_title": user.job_title,
            "bio": user.bio,
            "avatar": user.avatar,
            "is_superadmin": bool(user.is_superadmin),
            "created_at": _iso(user.created_at),
        },
    }


def read_user_settings(storage: ObjectStorageService, user_id: str) -> dict[str, Any] | None:
    try:
        content = storage.get_object(
            drive_settings.settings_prefix(user_id, SECTION), USER_SETTINGS_KEY
        )
    except StorageExceptions.ObjectNotFound:
        return None
    return json.loads(content)


def save_user_settings(
    storage: ObjectStorageService, user: UserInfo, now: datetime
) -> UserSettingsSaveResult:
    """Write ``user.json`` if it changed, archiving the previous version first."""
    return drive_settings.save_versioned(
        storage,
        user.id,
        SECTION,
        USER_SETTINGS_KEY,
        drive_settings.encode_json(user_settings_document(user)),
        now,
    )
