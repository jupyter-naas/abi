from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.services.auth.handlers import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.modules.schema import ModulesResponse
from naas_abi.apps.nexus.apps.api.app.services.modules.service import ModulesService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


@router.get("/", response_model=ModulesResponse)
async def list_modules() -> ModulesResponse:
    """Return installed modules and the full marketplace catalog."""
    return await ModulesService.list_modules()
