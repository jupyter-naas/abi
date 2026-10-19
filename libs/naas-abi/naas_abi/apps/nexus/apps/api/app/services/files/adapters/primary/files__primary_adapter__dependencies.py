from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, HTTPException, Request
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal
from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
    PostgresSessionRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.files.service import FilesService
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry
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


async def workspace_setting(workspace_id: str, setting: str) -> bool:
    """Whether the workspace row has ``setting`` (``platform_drive_enabled``,
    ``system_drive_enabled``) switched on. That is a domain rule of Nexus; who
    may use the drive is IAM's."""
    async with AsyncSessionLocal() as db:
        session_registry = PostgresSessionRegistry.instance()
        session_id = f"sess-{uuid4().hex}"
        session_registry.bind(session_id=session_id, db=db)
        token = session_registry.set_current_session(session_id)
        try:
            workspace = await ServiceRegistry.instance().workspaces.get_workspace(
                workspace_id=workspace_id
            )
        finally:
            session_registry.reset_current_session(token)
            session_registry.unbind(session_id)
    return workspace is not None and bool(getattr(workspace, setting, False))
