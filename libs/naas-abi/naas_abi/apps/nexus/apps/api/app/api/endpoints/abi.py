"""
ABI Server Configuration API
Manage external ABI servers per workspace.
"""

from datetime import datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import deprecated_encrypt
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import ABIServerModel
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


# ============ Pydantic Schemas ============


class ABIServer(BaseModel):
    """ABI Server model."""

    id: str
    workspace_id: str
    name: str
    endpoint: str
    enabled: bool
    created_at: datetime
    updated_at: datetime


class ABIServerCreate(BaseModel):
    """Create ABI server request."""

    name: str = Field(..., min_length=1, max_length=255)
    endpoint: str = Field(..., min_length=1)
    api_key: str | None = None


class ABIServerUpdate(BaseModel):
    """Update ABI server request."""

    name: str | None = Field(None, min_length=1, max_length=255)
    endpoint: str | None = Field(None, min_length=1)
    api_key: str | None = None
    enabled: bool | None = None


# ============ Helpers ============


def _to_abi_server(row: ABIServerModel) -> ABIServer:
    return ABIServer(
        id=row.id,
        workspace_id=row.workspace_id,
        name=row.name,
        endpoint=row.endpoint,
        enabled=row.enabled,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


# ============ Endpoints ============


@router.get(
    "/workspaces/{workspace_id}/abi-servers", dependencies=[guard("ListAbiServers", literal="-")]
)
async def list_abi_servers(
    workspace_id: str,
    db: AsyncSession = Depends(get_db),
) -> list[ABIServer]:
    """List all ABI servers for a workspace."""
    result = await db.execute(
        select(ABIServerModel).where(ABIServerModel.workspace_id == workspace_id)
    )
    return [_to_abi_server(row) for row in result.scalars().all()]


@router.post(
    "/workspaces/{workspace_id}/abi-servers", dependencies=[guard("CreateAbiServer", literal="-")]
)
async def create_abi_server(
    workspace_id: str,
    server: ABIServerCreate,
    db: AsyncSession = Depends(get_db),
) -> ABIServer:
    """Create a new ABI server for a workspace."""
    # Check if endpoint already exists for this workspace
    existing = await db.execute(
        select(ABIServerModel).where(
            ABIServerModel.workspace_id == workspace_id,
            ABIServerModel.endpoint == server.endpoint,
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="ABI server with this endpoint already exists")

    now = datetime.now(UTC).replace(tzinfo=None)
    server_id = f"abi-{uuid4().hex[:12]}"

    row = ABIServerModel(
        id=server_id,
        workspace_id=workspace_id,
        name=server.name,
        endpoint=server.endpoint,
        api_key=deprecated_encrypt(server.api_key) if server.api_key else None,
        enabled=True,
        created_at=now,
        updated_at=now,
    )

    db.add(row)
    await db.commit()

    return _to_abi_server(row)


@router.get(
    "/workspaces/{workspace_id}/abi-servers/{server_id}",
    dependencies=[guard("GetAbiServer", id="server_id")],
)
async def get_abi_server(
    workspace_id: str,
    server_id: str,
    db: AsyncSession = Depends(get_db),
) -> ABIServer:
    """Get a specific ABI server."""
    result = await db.execute(
        select(ABIServerModel).where(
            ABIServerModel.id == server_id,
            ABIServerModel.workspace_id == workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="ABI server not found")

    return _to_abi_server(row)


@router.put(
    "/workspaces/{workspace_id}/abi-servers/{server_id}",
    dependencies=[guard("UpdateAbiServer", id="server_id")],
)
async def update_abi_server(
    workspace_id: str,
    server_id: str,
    updates: ABIServerUpdate,
    db: AsyncSession = Depends(get_db),
) -> ABIServer:
    """Update an ABI server."""
    result = await db.execute(
        select(ABIServerModel).where(
            ABIServerModel.id == server_id,
            ABIServerModel.workspace_id == workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="ABI server not found")

    now = datetime.now(UTC).replace(tzinfo=None)

    if updates.name is not None:
        row.name = updates.name
    if updates.endpoint is not None:
        row.endpoint = updates.endpoint
    if updates.api_key is not None:
        row.api_key = deprecated_encrypt(updates.api_key) if updates.api_key else None
    if updates.enabled is not None:
        row.enabled = updates.enabled

    row.updated_at = now
    await db.commit()

    return _to_abi_server(row)


@router.delete(
    "/workspaces/{workspace_id}/abi-servers/{server_id}",
    dependencies=[guard("DeleteAbiServer", id="server_id")],
)
async def delete_abi_server(
    workspace_id: str,
    server_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete an ABI server."""
    result = await db.execute(
        select(ABIServerModel).where(
            ABIServerModel.id == server_id,
            ABIServerModel.workspace_id == workspace_id,
        )
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="ABI server not found")

    await db.delete(row)
    await db.commit()

    return {"status": "deleted"}
