from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import get_current_user_required
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.primary.providers__primary_adapter__schemas import (  # noqa: E501
    Model,
    ModelUpdate,
    Provider,
    to_model_schema,
    to_provider_schema,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.adapters.secondary.providers__secondary_adapter__postgres import (  # noqa: E501
    ModelCatalogSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.providers.service import ProviderService
from sqlalchemy.ext.asyncio import AsyncSession

# The catalog is the platform's, not a workspace's: no ``workspace_id`` here.
router = APIRouter(dependencies=[Depends(get_current_user_required)])


def get_provider_service(db: AsyncSession = Depends(get_db)) -> ProviderService:
    """Build a ProviderService backed by the Postgres model-catalog store."""
    return ProviderService(store=ModelCatalogSecondaryAdapterPostgres(db))


@router.get(
    "/available",
    dependencies=[guard("ListProviderModels", workspace=None, literal="-")],
)
async def list_available_providers(
    service: ProviderService = Depends(get_provider_service),
) -> list[Provider]:
    providers = await service.list_available_providers()
    return [to_provider_schema(provider) for provider in providers]


@router.get(
    "/models",
    dependencies=[guard("ListProviderModels", workspace=None, literal="-")],
)
async def list_models(
    service: ProviderService = Depends(get_provider_service),
) -> list[Model]:
    models = await service.list_models()
    return [to_model_schema(model) for model in models]


@router.get(
    "/models/{model_id:path}",
    dependencies=[guard("GetProviderModel", workspace=None, id="model_id")],
)
async def get_model(
    model_id: str,
    service: ProviderService = Depends(get_provider_service),
) -> Model:
    model = await service.get_model(canonical_or_model_id=model_id)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    return to_model_schema(model)


@router.patch(
    "/models/{model_id:path}",
    dependencies=[guard("UpdateProviderModel", workspace=None, id="model_id")],
)
async def update_model(
    model_id: str,
    body: ModelUpdate,
    service: ProviderService = Depends(get_provider_service),
) -> Model:
    updates = body.model_dump(exclude_unset=True)
    model = await service.update_model(canonical_or_model_id=model_id, updates=updates)
    if model is None:
        raise HTTPException(status_code=404, detail=f"Model {model_id!r} not found")
    return to_model_schema(model)
