"""
Workspaces API endpoints.
All endpoints require authentication. Workspace-specific endpoints require membership.
"""

import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User, get_current_user_required, get_workspace_role,
    require_workspace_access)
from naas_abi.apps.nexus.apps.api.app.api.endpoints.secrets import _encrypt
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (AgentConfigModel,
                                                     ConversationModel,
                                                     GraphEdgeModel,
                                                     GraphNodeModel,
                                                     OrganizationModel,
                                                     UserModel,
                                                     WorkspaceMemberModel,
                                                     WorkspaceModel)
from pydantic import BaseModel, Field
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


class Workspace(BaseModel):
    """Workspace model."""
    id: str
    name: str
    slug: str
    owner_id: str
    organization_id: str | None = None
    # Theme fields
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    # Inherited branding (from organization) – provided for convenience
    organization_logo_url: str | None = None
    organization_logo_rectangle_url: str | None = None


class WorkspaceCreate(BaseModel):
    """Create a new workspace."""
    name: str = Field(..., min_length=1, max_length=200)
    slug: str = Field(..., min_length=1, max_length=100, pattern=r'^[a-z0-9][a-z0-9\-]*[a-z0-9]$')
    organization_id: str | None = None
    # Optional theme fields
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None


def _to_schema(row: WorkspaceModel) -> Workspace:
    return Workspace(
        id=row.id, name=row.name, slug=row.slug,
        owner_id=row.owner_id, organization_id=row.organization_id,
        logo_url=row.logo_url, logo_emoji=row.logo_emoji,
        primary_color=row.primary_color, accent_color=row.accent_color,
        background_color=row.background_color, sidebar_color=row.sidebar_color,
        font_family=row.font_family,
        created_at=row.created_at, updated_at=row.updated_at,
    )


@router.get("")
async def list_workspaces(
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[Workspace]:
    """List workspaces the current user is a member of (or owns)."""
    result = await db.execute(
        select(WorkspaceModel)
        .outerjoin(WorkspaceMemberModel, WorkspaceModel.id == WorkspaceMemberModel.workspace_id)
        .where(
            (WorkspaceModel.owner_id == current_user.id)
            | (WorkspaceMemberModel.user_id == current_user.id)
        )
        .distinct()
        .order_by(WorkspaceModel.name)
    )
    rows = result.scalars().all()
    # Preload org logos for inheritance
    org_ids = {r.organization_id for r in rows if r.organization_id}
    org_logo_map: dict[str, tuple[str | None, str | None]] = {}
    if org_ids:
        org_res = await db.execute(
            select(OrganizationModel.id, OrganizationModel.logo_url, OrganizationModel.logo_rectangle_url)
            .where(OrganizationModel.id.in_(org_ids))
        )
        for oid, logo_url, logo_rect in org_res.all():
            org_logo_map[oid] = (logo_url, logo_rect)

    api_rows: list[Workspace] = []
    for row in rows:
        ws = _to_schema(row)
        if row.organization_id and row.organization_id in org_logo_map:
            logos = org_logo_map[row.organization_id]
            ws.organization_logo_url = logos[0]
            ws.organization_logo_rectangle_url = logos[1]
        api_rows.append(ws)
    return api_rows


@router.get("/{workspace_id}")
async def get_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Get a workspace by ID. Requires membership."""
    await require_workspace_access(current_user.id, workspace_id)
    result = await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    ws = _to_schema(row)
    if row.organization_id:
        org_res = await db.execute(
            select(OrganizationModel.logo_url, OrganizationModel.logo_rectangle_url)
            .where(OrganizationModel.id == row.organization_id)
        )
        logos = org_res.first()
        if logos:
            ws.organization_logo_url = logos[0]
            ws.organization_logo_rectangle_url = logos[1]
    return ws


@router.get("/slug/{slug}")
async def get_workspace_by_slug(
    slug: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Get a workspace by slug. Requires membership."""
    result = await db.execute(select(WorkspaceModel).where(WorkspaceModel.slug == slug))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(status_code=404, detail="Workspace not found")
    await require_workspace_access(current_user.id, row.id)
    ws = _to_schema(row)
    if row.organization_id:
        org_res = await db.execute(
            select(OrganizationModel.logo_url, OrganizationModel.logo_rectangle_url)
            .where(OrganizationModel.id == row.organization_id)
        )
        logos = org_res.first()
        if logos:
            ws.organization_logo_url = logos[0]
            ws.organization_logo_rectangle_url = logos[1]
    return ws


@router.post("")
async def create_workspace(
    workspace: WorkspaceCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Create a new workspace. The current user becomes the owner."""
    # Check slug uniqueness
    existing = await db.execute(select(WorkspaceModel).where(WorkspaceModel.slug == workspace.slug))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Slug already exists")

    workspace_id = f"ws-{uuid4().hex[:12]}"
    now = datetime.now(timezone.utc).replace(tzinfo=None)

    ws = WorkspaceModel(
        id=workspace_id, name=workspace.name, slug=workspace.slug,
        owner_id=current_user.id, organization_id=workspace.organization_id,
        logo_url=workspace.logo_url, logo_emoji=workspace.logo_emoji,
        primary_color=workspace.primary_color, accent_color=workspace.accent_color,
        background_color=workspace.background_color, sidebar_color=workspace.sidebar_color,
        font_family=workspace.font_family,
        created_at=now, updated_at=now,
    )
    db.add(ws)

    member = WorkspaceMemberModel(
        id=str(uuid4()), workspace_id=workspace_id,
        user_id=current_user.id, role="owner", created_at=now,
    )
    db.add(member)
    await db.flush()

    return _to_schema(ws)


@router.delete("/{workspace_id}")
async def delete_workspace(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Delete a workspace. Only the owner can delete."""
    role = await require_workspace_access(current_user.id, workspace_id)
    if role != "owner":
        raise HTTPException(status_code=403, detail="Only the workspace owner can delete the workspace")

    result = await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    await db.delete(ws)
    return {"status": "deleted"}


class WorkspaceUpdate(BaseModel):
    """Update workspace theme/branding."""
    name: str | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    sidebar_color: str | None = None
    font_family: str | None = None


@router.patch("/{workspace_id}")
async def update_workspace(
    workspace_id: str,
    updates: WorkspaceUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> Workspace:
    """Update workspace theme/branding. Requires admin or owner role."""
    role = await require_workspace_access(current_user.id, workspace_id)
    if role not in ("owner", "admin"):
        raise HTTPException(status_code=403, detail="Only admins can update workspace settings")

    result = await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
    ws = result.scalar_one_or_none()
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")

    update_data = updates.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(ws, field, value)
    ws.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    await db.flush()
    return _to_schema(ws)


@router.get("/{workspace_id}/stats")
async def get_workspace_stats(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get statistics for a workspace. Requires membership."""
    await require_workspace_access(current_user.id, workspace_id)

    result = await db.execute(select(WorkspaceModel).where(WorkspaceModel.id == workspace_id))
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Workspace not found")

    nodes = (await db.execute(
        select(func.count()).select_from(GraphNodeModel).where(GraphNodeModel.workspace_id == workspace_id)
    )).scalar() or 0

    edges = (await db.execute(
        select(func.count()).select_from(GraphEdgeModel).where(GraphEdgeModel.workspace_id == workspace_id)
    )).scalar() or 0

    convs = (await db.execute(
        select(func.count()).select_from(ConversationModel).where(ConversationModel.workspace_id == workspace_id)
    )).scalar() or 0

    agents = (await db.execute(
        select(func.count()).select_from(AgentConfigModel).where(AgentConfigModel.workspace_id == workspace_id)
    )).scalar() or 0

    return {"nodes": nodes, "edges": edges, "conversations": convs, "agents": agents}


# ============================================
# Workspace Members Management
# ============================================

class WorkspaceMember(BaseModel):
    """Workspace member model."""
    id: str
    workspace_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None


class WorkspaceMemberInvite(BaseModel):
    """Invite a user to a workspace."""
    email: str = Field(..., min_length=3, max_length=255)
    role: str = Field(default="member", pattern=r'^(admin|member|viewer)$')


@router.get("/{workspace_id}/members")
async def list_workspace_members(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[WorkspaceMember]:
    """List members of a workspace. Requires membership."""
    await require_workspace_access(current_user.id, workspace_id)
    
    # Query with user details joined
    query = text("""
        SELECT 
            wm.id, wm.workspace_id, wm.user_id, wm.role, wm.created_at,
            u.email, u.name
        FROM workspace_members wm
        JOIN users u ON wm.user_id = u.id
        WHERE wm.workspace_id = :workspace_id
        ORDER BY wm.created_at
    """)
    
    result = await db.execute(query, {"workspace_id": workspace_id})
    rows = result.fetchall()
    
    return [
        WorkspaceMember(
            id=row.id,
            workspace_id=row.workspace_id,
            user_id=row.user_id,
            role=row.role,
            email=row.email,
            name=row.name,
            created_at=row.created_at,
        )
        for row in rows
    ]


@router.post("/{workspace_id}/members/invite")
async def invite_workspace_member(
    workspace_id: str,
    invite: WorkspaceMemberInvite,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Invite a user to a workspace. Requires admin role."""
    # Check if current user is admin
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can invite members")
    
    # Check if user exists
    user_result = await db.execute(
        select(UserModel).where(UserModel.email == invite.email)
    )
    user = user_result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Check if already a member
    existing = await db.execute(
        select(WorkspaceMemberModel).where(
            (WorkspaceMemberModel.workspace_id == workspace_id) &
            (WorkspaceMemberModel.user_id == user.id)
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="User is already a member")
    
    # Add member
    member = WorkspaceMemberModel(
        id=str(uuid4()),
        workspace_id=workspace_id,
        user_id=user.id,
        role=invite.role,
    )
    db.add(member)
    await db.commit()
    
    return {"status": "invited", "member_id": member.id}


@router.delete("/{workspace_id}/members/{user_id}")
async def remove_workspace_member(
    workspace_id: str,
    user_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Remove a member from a workspace. Requires admin role."""
    # Check if current user is admin
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can remove members")
    
    # Cannot remove yourself
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot remove yourself")
    
    # Remove member
    result = await db.execute(
        select(WorkspaceMemberModel).where(
            (WorkspaceMemberModel.workspace_id == workspace_id) &
            (WorkspaceMemberModel.user_id == user_id)
        )
    )
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    await db.delete(member)
    await db.commit()
    
    return {"status": "removed"}


@router.patch("/{workspace_id}/members/{user_id}")
async def update_workspace_member(
    workspace_id: str,
    user_id: str,
    updates: dict,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update a workspace member's role. Requires admin role."""
    # Check if current user is admin
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ["admin", "owner"]:
        raise HTTPException(status_code=403, detail="Only admins can update members")
    
    # Get member
    result = await db.execute(
        select(WorkspaceMemberModel).where(
            (WorkspaceMemberModel.workspace_id == workspace_id) &
            (WorkspaceMemberModel.user_id == user_id)
        )
    )
    member = result.scalar_one_or_none()
    
    if not member:
        raise HTTPException(status_code=404, detail="Member not found")
    
    # Update role
    if 'role' in updates and updates['role'] in ['admin', 'member', 'viewer']:
        member.role = updates['role']
        await db.commit()
    
    return {"status": "updated"}


# ============================================
# Inference Servers
# ============================================

class InferenceServer(BaseModel):
    """Inference server model."""
    id: str
    workspace_id: str
    name: str
    type: str  # 'ollama', 'abi', 'vllm', 'llamacpp', 'custom'
    endpoint: str
    description: str | None = None
    enabled: bool = True
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class InferenceServerCreate(BaseModel):
    """Create a new inference server."""
    name: str = Field(..., min_length=1, max_length=200)
    type: str = Field(..., pattern=r'^(ollama|abi|vllm|llamacpp|custom)$')
    endpoint: str = Field(..., min_length=1)
    description: str | None = None
    enabled: bool = True
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None


class InferenceServerUpdate(BaseModel):
    """Update inference server."""
    name: str | None = None
    endpoint: str | None = None
    description: str | None = None
    enabled: bool | None = None
    api_key: str | None = None
    health_path: str | None = None
    models_path: str | None = None


@router.get("/{workspace_id}/servers")
async def list_inference_servers(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> list[InferenceServer]:
    """List all inference servers in a workspace."""
    from naas_abi.apps.nexus.apps.api.app.models import InferenceServerModel

    # Check access
    await require_workspace_access(current_user.id, workspace_id)
    
    # Get servers
    result = await db.execute(
        select(InferenceServerModel)
        .where(InferenceServerModel.workspace_id == workspace_id)
        .order_by(InferenceServerModel.created_at.desc())
    )
    servers = result.scalars().all()
    
    return [
        InferenceServer(
            id=s.id,
            workspace_id=s.workspace_id,
            name=s.name,
            type=s.type,
            endpoint=s.endpoint,
            description=s.description,
            enabled=s.enabled,
            api_key=s.api_key,
            health_path=s.health_path,
            models_path=s.models_path,
            created_at=s.created_at,
            updated_at=s.updated_at,
        )
        for s in servers
    ]


@router.post("/{workspace_id}/servers")
async def create_inference_server(
    workspace_id: str,
    server_data: InferenceServerCreate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> InferenceServer:
    """Create a new inference server."""
    from naas_abi.apps.nexus.apps.api.app.models import InferenceServerModel

    # Check access (admin only)
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ['admin', 'owner']:
        raise HTTPException(status_code=403, detail="Only admins can add servers")
    
    # Create server
    server = InferenceServerModel(
        id=str(uuid4()),
        workspace_id=workspace_id,
        name=server_data.name,
        type=server_data.type,
        endpoint=server_data.endpoint.rstrip('/'),  # Remove trailing slash
        description=server_data.description,
        enabled=server_data.enabled,
        api_key=_encrypt(server_data.api_key) if server_data.api_key else None,
        health_path=server_data.health_path,
        models_path=server_data.models_path,
        created_at=datetime.now(timezone.utc).replace(tzinfo=None),
        updated_at=datetime.now(timezone.utc).replace(tzinfo=None),
    )
    db.add(server)
    await db.commit()
    await db.refresh(server)
    
    return InferenceServer(
        id=server.id,
        workspace_id=server.workspace_id,
        name=server.name,
        type=server.type,
        endpoint=server.endpoint,
        description=server.description,
        enabled=server.enabled,
        api_key=server.api_key,
        health_path=server.health_path,
        models_path=server.models_path,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.patch("/{workspace_id}/servers/{server_id}")
async def update_inference_server(
    workspace_id: str,
    server_id: str,
    updates: InferenceServerUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> InferenceServer:
    """Update an inference server."""
    from naas_abi.apps.nexus.apps.api.app.models import InferenceServerModel

    # Check access (admin only)
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ['admin', 'owner']:
        raise HTTPException(status_code=403, detail="Only admins can update servers")
    
    # Get server
    result = await db.execute(
        select(InferenceServerModel).where(
            (InferenceServerModel.id == server_id) &
            (InferenceServerModel.workspace_id == workspace_id)
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Update fields
    if updates.name is not None:
        server.name = updates.name
    if updates.endpoint is not None:
        server.endpoint = updates.endpoint.rstrip('/')
    if updates.description is not None:
        server.description = updates.description
    if updates.enabled is not None:
        server.enabled = updates.enabled
    if updates.api_key is not None:
        server.api_key = _encrypt(updates.api_key) if updates.api_key else None
    if updates.health_path is not None:
        server.health_path = updates.health_path
    if updates.models_path is not None:
        server.models_path = updates.models_path
    
    server.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(server)
    
    return InferenceServer(
        id=server.id,
        workspace_id=server.workspace_id,
        name=server.name,
        type=server.type,
        endpoint=server.endpoint,
        description=server.description,
        enabled=server.enabled,
        api_key=server.api_key,
        health_path=server.health_path,
        models_path=server.models_path,
        created_at=server.created_at,
        updated_at=server.updated_at,
    )


@router.delete("/{workspace_id}/servers/{server_id}")
async def delete_inference_server(
    workspace_id: str,
    server_id: str,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Delete an inference server."""
    from naas_abi.apps.nexus.apps.api.app.models import InferenceServerModel

    # Check access (admin only)
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ['admin', 'owner']:
        raise HTTPException(status_code=403, detail="Only admins can delete servers")
    
    # Get server
    result = await db.execute(
        select(InferenceServerModel).where(
            (InferenceServerModel.id == server_id) &
            (InferenceServerModel.workspace_id == workspace_id)
        )
    )
    server = result.scalar_one_or_none()
    
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    
    # Delete
    await db.delete(server)
    await db.commit()
    
    return {"status": "deleted"}


# Create uploads directory if it doesn't exist
UPLOAD_DIR = Path("uploads/logos")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Allowed image extensions
ALLOWED_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
MAX_FILE_SIZE = 5 * 1024 * 1024  # 5MB


@router.post("/{workspace_id}/upload-logo")
async def upload_workspace_logo(
    workspace_id: str,
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a logo image for the workspace."""
    # Check access (admin only)
    role = await get_workspace_role(current_user.id, workspace_id)
    if role not in ['admin', 'owner']:
        raise HTTPException(status_code=403, detail="Only admins can upload logos")
    
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")
    
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_EXTENSIONS)}"
        )
    
    # Check file size
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 5MB)")
    
    # Generate unique filename
    unique_filename = f"{workspace_id}-{uuid4().hex[:8]}{ext}"
    file_path = UPLOAD_DIR / unique_filename
    
    # Save file
    with open(file_path, "wb") as f:
        f.write(content)
    
    # Generate URL (assuming nginx serves /uploads)
    logo_url = f"/uploads/logos/{unique_filename}"
    
    # Update workspace
    result = await db.execute(
        select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
    )
    workspace = result.scalar_one_or_none()
    if not workspace:
        # Clean up uploaded file
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="Workspace not found")
    
    # Delete old logo file if it exists and is a local upload
    if workspace.logo_url and workspace.logo_url.startswith("/uploads/logos/"):
        old_file = UPLOAD_DIR / os.path.basename(workspace.logo_url)
        old_file.unlink(missing_ok=True)
    
    workspace.logo_url = logo_url
    workspace.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
    await db.commit()
    await db.refresh(workspace)
    
    return {
        "logo_url": logo_url,
        "filename": unique_filename,
    }
