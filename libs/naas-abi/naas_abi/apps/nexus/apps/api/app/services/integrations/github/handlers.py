from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_current_user_required,
    require_superadmin,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.integrations.github.schema import (
    GitHubAppInstallStartRequest,
    GitHubAppInstallStartResponse,
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


@router.post("/app/install", response_model=GitHubAppInstallStartResponse)
async def github_app_install_start(
    body: GitHubAppInstallStartRequest | None = None,
    _: User = Depends(require_superadmin),
) -> GitHubAppInstallStartResponse:
    """Return the GitHub App install URL (org/repo picker)."""
    payload = body or GitHubAppInstallStartRequest()
    try:
        result = GitHubConnectService.start_app_install(
            return_to=payload.return_to,
            workspace_id=payload.workspace_id,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return GitHubAppInstallStartResponse(**result)


@router.get("/app/setup")
async def github_app_setup(
    installation_id: str = Query(..., min_length=1),
    setup_action: str | None = Query(None),
    state: str | None = Query(None),
) -> RedirectResponse:
    """GitHub redirects here after App install. Validates state; no session cookie required."""
    try:
        result = await GitHubConnectService.complete_app_setup(
            installation_id=installation_id,
            state=state,
            setup_action=setup_action,
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=502,
            detail=f"GitHub App setup failed: {exc}",
        ) from exc
    return RedirectResponse(url=result["redirect_to"], status_code=302)
