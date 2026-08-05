from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.runtime.schema import (
    OsStatusResponse,
    RestartOsResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.runtime.service import RuntimeService

router = APIRouter()


@router.get("/os-status", response_model=OsStatusResponse)
async def os_status(
    _: User = Depends(get_current_user_required),
) -> OsStatusResponse:
    """Whether a dev runtime is present and an OS restart is in progress."""
    return await RuntimeService.os_status()


@router.post("/restart-os", response_model=RestartOsResponse)
async def restart_os(
    _: User = Depends(require_superadmin),
) -> RestartOsResponse:
    """Restart the ABI runtime (Reload OS). Superadmin only."""
    try:
        return await RuntimeService.restart_os()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
