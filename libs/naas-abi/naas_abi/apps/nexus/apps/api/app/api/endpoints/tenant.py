"""
Public tenant configuration endpoint.

Returns branding values (tab title, favicon) configured in config.yaml
so the frontend can apply them without authentication.
"""

from fastapi import APIRouter
from naas_abi.apps.nexus.apps.api.app.services.tenant import TenantResponse, TenantService

router = APIRouter()


@router.get("", response_model=TenantResponse)
async def get_tenant_config() -> TenantResponse:
    """Public endpoint — no auth required."""
    return await TenantService.get_tenant_config()
