"""Code workdir sync FastAPI primary adapter."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.code.adapters.primary.code__primary_adapter__dependencies import (
    get_code_workdir_sync_service,
)
from naas_abi.apps.nexus.apps.api.app.services.code.workdir_sync_service import (
    CodeWorkdirSyncService,
)

sync_router = APIRouter(dependencies=[Depends(get_current_user_required)])


@sync_router.post("/sync")
async def sync_code_workdir(
    direction: str = Query(default="both", pattern="^(pull|push|both)$"),
    current_user: User = Depends(get_current_user_required),
    sync_service: CodeWorkdirSyncService = Depends(get_code_workdir_sync_service),
):
    result = sync_service.sync(current_user.id, direction=direction)
    return {
        "localPath": result.local_path,
        "remoteRoot": result.remote_root,
        "filesPulled": result.files_pulled,
        "filesPushed": result.files_pushed,
    }
