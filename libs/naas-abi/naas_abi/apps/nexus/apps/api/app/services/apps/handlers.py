from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.apps.schema import AppsResponse
from naas_abi.apps.nexus.apps.api.app.services.apps.service import AppsService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


@router.get("/", response_model=AppsResponse)
async def list_apps() -> AppsResponse:
    """Return every app discovered from marketplace module manifests."""
    return await AppsService.list_apps()
