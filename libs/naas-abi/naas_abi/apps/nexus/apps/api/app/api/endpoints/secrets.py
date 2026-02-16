"""
Secrets API endpoints - Server-side secret storage.

Secrets are stored per workspace. Only workspace admins/owners can manage them.
Values are encrypted at rest using Fernet (AES-128-CBC + HMAC-SHA256)
and never sent to the client in full.

Async sessions with SQLAlchemy ORM.
"""

import base64
import hashlib
from datetime import datetime
from typing import Literal
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
    require_workspace_access,
)
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import SecretModel
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter(dependencies=[Depends(get_current_user_required)])



# ============ Schemas ============

class SecretCreate(BaseModel):
    """Create a new secret."""
    workspace_id: str = Field(..., min_length=1, max_length=100)
    key: str = Field(..., min_length=1, max_length=200, pattern=r'^[\w\-. ]+$')
    value: str = Field(..., min_length=1, max_length=50_000)
    description: str = Field(default="", max_length=1000)
    category: Literal["api_keys", "credentials", "tokens", "other"] = "other"


class SecretUpdate(BaseModel):
    """Update a secret value."""
    value: str | None = Field(None, min_length=1, max_length=50_000)
    description: str | None = Field(None, max_length=1000)


class SecretResponse(BaseModel):
    """Secret returned to client - value is masked."""
    id: str
    workspace_id: str
    key: str
    masked_value: str
    description: str
    category: str
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SecretBulkImport(BaseModel):
    """Bulk import secrets from .env format."""
    workspace_id: str = Field(..., min_length=1, max_length=100)
    env_content: str = Field(..., min_length=1, max_length=500_000)


# ============ Encryption Helpers ============

def _get_fernet() -> Fernet:
    key_hash = hashlib.sha256(settings.secret_key.encode('utf-8')).digest()
    fernet_key = base64.urlsafe_b64encode(key_hash)
    return Fernet(fernet_key)


def _encrypt(value: str) -> str:
    f = _get_fernet()
    return f.encrypt(value.encode('utf-8')).decode('utf-8')


def _decrypt(encrypted_value: str) -> str:
    f = _get_fernet()
    return f.decrypt(encrypted_value.encode('utf-8')).decode('utf-8')


def _try_decrypt(encrypted_value: str) -> str | None:
    try:
        return _decrypt(encrypted_value)
    except (InvalidToken, Exception):
        return None


def _mask_value(value: str) -> str:
    if len(value) <= 8:
        return "****"
    return value[:4] + "****" + value[-4:]


def _infer_category(key: str) -> str:
    key_upper = key.upper()
    if "API_KEY" in key_upper or "APIKEY" in key_upper:
        return "api_keys"
    if "TOKEN" in key_upper or "JWT" in key_upper:
        return "tokens"
    if "PASSWORD" in key_upper or "SECRET" in key_upper or "CREDENTIAL" in key_upper:
        return "credentials"
    return "other"


def _to_response(row: SecretModel) -> SecretResponse:
    decrypted = _try_decrypt(row.encrypted_value)
    masked = _mask_value(decrypted) if decrypted else "****"
    return SecretResponse(
        id=row.id, workspace_id=row.workspace_id, key=row.key,
        masked_value=masked, description=row.description or "",
        category=row.category, created_at=row.created_at, updated_at=row.updated_at,
    )


# ============ Endpoints ============

@router.get("/{workspace_id}")
async def list_secrets(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[SecretResponse]:
    """List all secrets for a workspace (values are masked)."""
    await require_workspace_access(current_user.id, workspace_id)
    result = await db.execute(
        select(SecretModel).where(SecretModel.workspace_id == workspace_id).order_by(SecretModel.key)
    )
    return [_to_response(r) for r in result.scalars().all()]


@router.post("")
async def create_secret(
    secret: SecretCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SecretResponse:
    """Create a new secret. Requires workspace admin/owner access."""
    role = await require_workspace_access(current_user.id, secret.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    # Check uniqueness
    existing = await db.execute(
        select(SecretModel).where(
            SecretModel.workspace_id == secret.workspace_id,
            SecretModel.key == secret.key,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Secret with key '{secret.key}' already exists")

    now = datetime.now(UTC).replace(tzinfo=None)
    row = SecretModel(
        id=str(uuid4()), workspace_id=secret.workspace_id, key=secret.key,
        encrypted_value=_encrypt(secret.value), description=secret.description,
        category=secret.category or _infer_category(secret.key),
        created_at=now, updated_at=now,
    )
    db.add(row)
    await db.commit()

    return SecretResponse(
        id=row.id, workspace_id=row.workspace_id, key=row.key,
        masked_value=_mask_value(secret.value), description=secret.description,
        category=row.category, created_at=now, updated_at=now,
    )


@router.put("/{secret_id}")
async def update_secret(
    secret_id: str,
    update: SecretUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> SecretResponse:
    """Update a secret value or description."""
    result = await db.execute(select(SecretModel).where(SecretModel.id == secret_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Secret not found")

    role = await require_workspace_access(current_user.id, row.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    now = datetime.now(UTC).replace(tzinfo=None)
    row.updated_at = now

    if update.value is not None:
        row.encrypted_value = _encrypt(update.value)
    if update.description is not None:
        row.description = update.description

    await db.commit()
    return _to_response(row)


@router.delete("/{secret_id}")
async def delete_secret(
    secret_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete a secret."""
    result = await db.execute(select(SecretModel).where(SecretModel.id == secret_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Secret not found")

    role = await require_workspace_access(current_user.id, row.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    await db.delete(row)
    return {"status": "deleted"}


@router.post("/import")
async def bulk_import_secrets(
    data: SecretBulkImport,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Bulk import secrets from .env format content."""
    role = await require_workspace_access(current_user.id, data.workspace_id)
    if role not in ("admin", "owner"):
        raise HTTPException(status_code=403, detail="Only admins and owners can manage secrets")

    imported = 0
    updated = 0
    now = datetime.now(UTC).replace(tzinfo=None)

    for line in data.env_content.split("\n"):
        trimmed = line.strip()
        if not trimmed or trimmed.startswith("#"):
            continue

        eq_idx = trimmed.find("=")
        if eq_idx == -1:
            continue

        key = trimmed[:eq_idx].strip()
        value = trimmed[eq_idx + 1:].strip()

        if (value.startswith('"') and value.endswith('"')) or \
           (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]

        if not key:
            continue

        encrypted = _encrypt(value)

        result = await db.execute(
            select(SecretModel).where(
                SecretModel.workspace_id == data.workspace_id,
                SecretModel.key == key,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.encrypted_value = encrypted
            existing.updated_at = now
            updated += 1
        else:
            db.add(SecretModel(
                id=str(uuid4()), workspace_id=data.workspace_id, key=key,
                encrypted_value=encrypted, description="",
                category=_infer_category(key), created_at=now, updated_at=now,
            ))
            imported += 1

    await db.commit()
    return {"imported": imported, "updated": updated}


@router.get("/test-public")
async def test_public_endpoint() -> dict:
    """Public test endpoint to verify routing works."""
    return {"message": "Public secrets endpoint working!"}


# Note: Public debug endpoints were intentionally removed for security.


async def resolve_secret_async(db: AsyncSession, workspace_id: str, key: str) -> str | None:
    """Resolve a secret value by workspace and key (async). For internal use only."""
    result = await db.execute(
        select(SecretModel).where(
            SecretModel.workspace_id == workspace_id,
            SecretModel.key == key,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        return None
    return _try_decrypt(row.encrypted_value)
