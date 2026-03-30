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
