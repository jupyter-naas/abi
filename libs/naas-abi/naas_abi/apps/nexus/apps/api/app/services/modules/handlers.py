from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import get_settings
from naas_abi.apps.nexus.apps.api.app.services.modules.schema import (
    InstallModuleResponse,
    MarketplaceConfigResponse,
    ModulesResponse,
)
from naas_abi.apps.nexus.apps.api.app.services.modules.service import ModulesService

router = APIRouter(dependencies=[Depends(get_current_user_required)])


@router.get("/", response_model=ModulesResponse)
async def list_modules() -> ModulesResponse:
    """Return installed modules and the full marketplace catalog."""
    return await ModulesService.list_modules()


@router.post("/install/{module_path:path}", response_model=InstallModuleResponse)
async def install_module(module_path: str) -> InstallModuleResponse:
    """
    Enable a marketplace module in config.yaml.

    Requires an API restart before tools/agents from the module are available.
    """
    try:
        return await ModulesService.install_module(module_path)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    except OSError as exc:
        raise HTTPException(
            status_code=503,
            detail=(
                f"Cannot write module config ({exc}). On GCP, enable the module in "
                "config.gcp.yaml and redeploy, or connect GitHub if the module is "
                "already listed as installed."
            ),
        ) from exc


@router.get("/config", response_model=MarketplaceConfigResponse)
async def get_marketplace_config() -> MarketplaceConfigResponse:
    """Return marketplace configuration: pricing, usage tiers, model token costs."""
    return MarketplaceConfigResponse(config=get_settings().marketplace)
