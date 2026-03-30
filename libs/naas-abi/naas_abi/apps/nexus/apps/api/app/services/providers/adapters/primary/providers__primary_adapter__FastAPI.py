from __future__ import annotations

from fastapi import APIRouter, Depends
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import User, get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary.providers__primary_adapter__schemas import (  # noqa: E501
    Provider,
    to_provider_schema,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.secondary import (
    ProvidersSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(dependencies=[Depends(get_current_user_required)])


def get_provider_service(db: AsyncSession = Depends(get_db)) -> ProviderService:
    return ProviderService(adapter=ProvidersSecondaryAdapterPostgres(db=db))


@router.get("/available")
async def list_available_providers(
    current_user: User = Depends(get_current_user_required),
    service: ProviderService = Depends(get_provider_service),
) -> list[Provider]:
    providers = await service.list_available_providers(user_id=current_user.id)
    return [to_provider_schema(provider) for provider in providers]
