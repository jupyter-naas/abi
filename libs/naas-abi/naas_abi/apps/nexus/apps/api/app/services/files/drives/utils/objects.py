"""Object-storage checks shared by every drive."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def isoformat(value: Any) -> str | None:
    return value.isoformat() if isinstance(value, datetime) else None


def object_exists(storage: ObjectStorageService, prefix: str, key: str) -> bool:
    try:
        storage.get_object(prefix, key)
        return True
    except Exceptions.ObjectNotFound:
        return False
