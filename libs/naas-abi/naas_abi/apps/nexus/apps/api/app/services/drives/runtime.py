"""Build the drives' service from the engine: its object storage configuration and
adapter. Tests override ``get_drive_service``."""

from __future__ import annotations

from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.drives.adapters.secondary.object_storage import (
    ObjectStorageDrive,
)
from naas_abi.apps.nexus.apps.api.app.services.drives.service import DriveService


def _engine() -> Any:
    from naas_abi import ABIModule

    return ABIModule.get_instance().engine


def _object_storage_adapter() -> Any:
    """The loaded adapter behind the kernel's object storage service."""
    return _engine().services.object_storage.adapter


def get_drive_service() -> DriveService:
    configuration = _engine().configuration.services.object_storage.object_storage_adapter
    return DriveService([ObjectStorageDrive(configuration, _object_storage_adapter)])
