"""Secrets FastAPI primary adapter."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.iam.port import RequestContext, TokenData
from naas_abi.apps.nexus.apps.api.app.services.secrets.adapters.secondary.postgres import (
    SecretsSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.secrets__schema import (
    SecretAlreadyExistsError,
    SecretBulkImportInput,
    SecretCreateInput,
    SecretNotFoundError,
    SecretOutput,
    SecretUpdateInput,
)
from naas_abi.apps.nexus.apps.api.app.services.secrets.service import SecretsService
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(dependencies=[Depends(get_current_user_required)])


class SecretsFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router


def get_secrets_service(db: AsyncSession = Depends(get_db)) -> SecretsService:
    return SecretsService(
        adapter=SecretsSecondaryAdapterPostgres(db=db),
        workspace_access_checker=require_workspace_access,
    )


def request_context(current_user: User) -> RequestContext:
    return RequestContext(
        token_data=TokenData(user_id=current_user.id, scopes={"*"}, is_authenticated=True)
    )


class SecretCreate(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    key: str = Field(..., min_length=1, max_length=200, pattern=r"^[\w\-. ]+$")
    value: str = Field(..., min_length=1, max_length=50_000)
    description: str = Field(default="", max_length=1000)
    category: Literal["api_keys", "credentials", "tokens", "other"] = "other"


class SecretUpdate(BaseModel):
    value: str | None = Field(None, min_length=1, max_length=50_000)
    description: str | None = Field(None, max_length=1000)


class SecretResponse(BaseModel):
    id: str
    workspace_id: str
    key: str
    masked_value: str
    description: str
    category: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SecretBulkImport(BaseModel):
    workspace_id: str = Field(..., min_length=1, max_length=100)
    env_content: str = Field(..., min_length=1, max_length=500_000)


def _to_secret_response(record: SecretOutput) -> SecretResponse:
    return SecretResponse(
        id=record.id,
        workspace_id=record.workspace_id,
        key=record.key,
        masked_value=record.masked_value,
        description=record.description,
        category=record.category,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


@router.get("/{workspace_id}")
async def list_secrets(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    service: SecretsService = Depends(get_secrets_service),
) -> list[SecretResponse]:
    await require_workspace_access(current_user.id, workspace_id)
    rows = await service.list_secrets(
        context=request_context(current_user),
        workspace_id=workspace_id,
    )
    return [_to_secret_response(row) for row in rows]


@router.post("")
async def create_secret(
    secret: SecretCreate,
    current_user: User = Depends(get_current_user_required),
    service: SecretsService = Depends(get_secrets_service),
) -> SecretResponse:
    role = await require_workspace_access(current_user.id, secret.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    try:
        row = await service.create_secret(
            context=request_context(current_user),
            secret=SecretCreateInput(
                workspace_id=secret.workspace_id,
                key=secret.key,
                value=secret.value,
                description=secret.description,
                category=secret.category,
            ),
            now=datetime.now(UTC).replace(tzinfo=None),
        )
    except SecretAlreadyExistsError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Secret with key '{exc.key}' already exists",
        ) from exc
    return _to_secret_response(row)


@router.put("/{secret_id}")
async def update_secret(
    secret_id: str,
    update: SecretUpdate,
    current_user: User = Depends(get_current_user_required),
    service: SecretsService = Depends(get_secrets_service),
) -> SecretResponse:
    row = await service.adapter.get_by_id(secret_id)
    if not row:
        raise HTTPException(status_code=404, detail="Secret not found")

    role = await require_workspace_access(current_user.id, row.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    try:
        updated = await service.update_secret(
            context=request_context(current_user),
            secret_id=secret_id,
            update=SecretUpdateInput(
                value=update.value,
                description=update.description,
            ),
            now=datetime.now(UTC).replace(tzinfo=None),
        )
    except SecretNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Secret not found") from exc
    return _to_secret_response(updated)


@router.delete("/{secret_id}")
async def delete_secret(
    secret_id: str,
    current_user: User = Depends(get_current_user_required),
    service: SecretsService = Depends(get_secrets_service),
) -> dict:
    row = await service.adapter.get_by_id(secret_id)
    if not row:
        raise HTTPException(status_code=404, detail="Secret not found")

    role = await require_workspace_access(current_user.id, row.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    try:
        await service.delete_secret(
            context=request_context(current_user),
            secret_id=secret_id,
        )
    except SecretNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Secret not found") from exc
    return {"status": "deleted"}


@router.post("/import")
async def bulk_import_secrets(
    data: SecretBulkImport,
    current_user: User = Depends(get_current_user_required),
    service: SecretsService = Depends(get_secrets_service),
) -> dict:
    role = await require_workspace_access(current_user.id, data.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    result = await service.bulk_import(
        context=request_context(current_user),
        data=SecretBulkImportInput(
            workspace_id=data.workspace_id,
            env_content=data.env_content,
        ),
        now=datetime.now(UTC).replace(tzinfo=None),
    )
    return {"imported": result.imported, "updated": result.updated}


@router.get("/test-public")
async def test_public_endpoint() -> dict:
    return {"message": "Public secrets endpoint working!"}
