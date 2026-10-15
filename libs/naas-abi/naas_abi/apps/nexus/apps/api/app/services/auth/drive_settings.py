"""A user's settings files in their own drive, with archived previous versions.

``naas_abi/my-drive/<user_id>/.settings/<section>/`` holds the current file(s);
``.settings/<section>/archives/<ts>_<name>`` keeps every previous version
(``files.drives.utils.versioned_files``). Used by ``avatar_store`` (pictures),
``user_settings_store`` (``user.json``) and ``user_drive_profile``.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils import versioned_files
from naas_abi.apps.nexus.apps.api.app.services.files.drives.utils.drive_roots import (
    my_drive_root,
)
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

VersionedSaveResult = versioned_files.VersionedSaveResult


def settings_prefix(user_id: str, section: str) -> str:
    return f"{my_drive_root(user_id)}/.settings/{section}"


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
    return versioned_files.save_versioned(
        storage, settings_prefix(user_id, section), key, content, now
    )
