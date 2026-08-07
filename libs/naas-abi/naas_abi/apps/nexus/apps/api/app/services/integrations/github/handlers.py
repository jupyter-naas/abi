from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.integrations.github.schema import (
    GitHubConnectStatusResponse,
    GitHubDevicePollResponse,
    GitHubDeviceStartResponse,
    GitHubTokenInput,
)
from naas_abi.apps.nexus.apps.api.app.services.integrations.github.service import (
    GitHubConnectService,
)

router = APIRouter()


@router.get("/status", response_model=GitHubConnectStatusResponse)
async def github_connect_status(
    _: User = Depends(get_current_user_required),
) -> GitHubConnectStatusResponse:
    return GitHubConnectStatusResponse(**(await GitHubConnectService.status()))


@router.delete("/token")
async def github_disconnect(
    _: User = Depends(require_superadmin),
) -> dict:
    return GitHubConnectService.disconnect()


@router.post("/device/start", response_model=GitHubDeviceStartResponse)
async def github_device_start(
    _: User = Depends(require_superadmin),
) -> GitHubDeviceStartResponse:
    try:
        payload = await GitHubConnectService.start_device_flow()
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"Failed to start GitHub device authorization: {exc}",
        ) from exc
    return GitHubDeviceStartResponse(**payload)


@router.post("/device/poll/{session_id}", response_model=GitHubDevicePollResponse)
async def github_device_poll(
    session_id: str,
    _: User = Depends(require_superadmin),
) -> GitHubDevicePollResponse:
    payload = await GitHubConnectService.poll_device_flow(session_id)
    return GitHubDevicePollResponse(**payload)


@router.post("/token")
async def github_save_token(
    body: GitHubTokenInput,
    _: User = Depends(require_superadmin),
) -> dict:
    try:
        return await GitHubConnectService.save_personal_access_token(body.token)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
