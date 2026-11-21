from __future__ import annotations

from fastapi import Depends, HTTPException, Request
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService


def get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage

    try:
        from naas_abi import ABIModule

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:  # pragma: no cover - runtime protection
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized. Load API through naas_abi.ABIModule.",
        ) from exc


def get_files_service(
    storage: ObjectStorageService = Depends(get_object_storage),
) -> FilesService:
    return FilesService(storage=storage)


async def may_use_platform_files(user_id: str) -> bool:
    """Whether ``user_id`` may open Platform Files: IAM's ``nexus:ListPlatformFiles``
    at the platform, decided as ``GET /api/files/views`` decides it. A workspace gives
    it to its people (Workspace settings > General › Platform Files, #1590). The
    supported check for a module that lets a user reach the platform drive with their
    own token; it replaces ``workspace_setting(..., "platform_drive_enabled")``."""
    from naas_abi.apps.nexus.apps.api.app.services.iam import authz

    return await authz.allowed("ListPlatformFiles", user=user_id, id=("platform",))
