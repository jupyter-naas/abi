from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.config import get_settings
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares, guard
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.runtime import get_iam_admin_service
from naas_abi.apps.nexus.apps.api.app.services.modules import scopes
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


@router.get("/scopes", dependencies=[declares("ListModuleScopes")])
async def list_module_scopes(
    workspace_id: str | None = None,
    organization_id: str | None = None,
    current_user: User = Depends(get_current_user_required),
) -> dict[str, Any]:
    """Every module with its agents, apps, workflows, pipelines and declared
    actions, as the scopes a policy grants (``modules/scopes.py``): for the
    admins of the workspace or the organization named and whoever may write
    policies there, narrowed to what the caller may grant there."""
    if not workspace_id and not organization_id:
        raise HTTPException(status_code=422, detail="Name a workspace_id or an organization_id")
    org = None if workspace_id else organization_id
    container = await authz.AUTHZ.where(workspace=workspace_id, org=org)
    admin = get_iam_admin_service()
    # Its admins, or whoever builds policies there.
    if container is None or not await admin.writes_policies(current_user, container):
        await authz.require(
            "ListModuleScopes", user=current_user, workspace=workspace_id, org=org, id="-"
        )
    if container is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    # Only what the caller may grant there: nothing lists more to someone who
    # may grant less (IAM's ``grantable``, as the caller).
    grantable = await admin.grantable(current_user, container)
    return {"modules": scopes.granted(await scopes.gather(), grantable["catalogs"])}
