from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import get_settings
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.modules.schema import (
    MarketplaceConfigResponse,
    ModulesResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.modules.service import ModulesService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


@router.get(
    "/",
    response_model=ModulesResponse,
    dependencies=[guard("ListModules", literal="-")],
)
async def list_modules(workspace_id: str) -> ModulesResponse:
    """Return installed modules and the full marketplace catalog, for a workspace
    whose members may open the marketplace."""
    return await ModulesService.list_modules()


@router.get(
    "/config",
    response_model=MarketplaceConfigResponse,
    dependencies=[guard("GetMarketplaceConfig", literal="-")],
)
async def get_marketplace_config(workspace_id: str) -> MarketplaceConfigResponse:
    """Return marketplace configuration: pricing, usage tiers, model token costs."""
    return MarketplaceConfigResponse(config=get_settings().marketplace)
