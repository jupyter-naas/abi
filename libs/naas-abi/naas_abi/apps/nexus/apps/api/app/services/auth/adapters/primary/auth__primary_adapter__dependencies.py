from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from naas_abi.apps.nexus.apps.api.app.core.database import AsyncSessionLocal, get_db
from naas_abi.apps.nexus.apps.api.app.core.postgres_session_registry import (
    PostgresSessionRegistry,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.secondary.postgres import (
    AuthSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService, decode_token
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry
from naas_abi.apps.nexus.apps.api.app.services.workspaces import WorkspacePermissionError
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def to_user_schema(user: AuthUserRecord) -> User:
    return User(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar=user.avatar,
        company=user.company,
        role=user.role,
        bio=user.bio,
        created_at=user.created_at,
    )


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(adapter=AuthSecondaryAdapterPostgres(db=db))


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    user = await auth_service.get_user_from_access_token(token)
    if user is None:
        return None
    return to_user_schema(user)


async def get_current_user_required(current_user: User | None = Depends(get_current_user)) -> User:
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return current_user


async def get_workspace_role(user_id: str, workspace_id: str) -> str | None:
    async with AsyncSessionLocal() as db:
        registry = ServiceRegistry.instance()
        session_registry = PostgresSessionRegistry.instance()
        session_id = f"sess-{uuid4().hex}"
        session_registry.bind(session_id=session_id, db=db)
        token = session_registry.set_current_session(session_id)
        try:
            return await registry.workspaces.get_workspace_role(
                user_id=user_id,
                workspace_id=workspace_id,
            )
        finally:
            session_registry.reset_current_session(token)
            session_registry.unbind(session_id)


async def require_workspace_access(user_id: str, workspace_id: str) -> str:
    async with AsyncSessionLocal() as db:
        registry = ServiceRegistry.instance()
        session_registry = PostgresSessionRegistry.instance()
        session_id = f"sess-{uuid4().hex}"
        session_registry.bind(session_id=session_id, db=db)
        token = session_registry.set_current_session(session_id)
        try:
            return await registry.workspaces.require_workspace_access(
                user_id=user_id,
                workspace_id=workspace_id,
            )
        except WorkspacePermissionError as exc:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this workspace",
            ) from exc
        finally:
            session_registry.reset_current_session(token)
            session_registry.unbind(session_id)


async def require_workspace_platform_drive(user_id: str, workspace_id: str) -> None:
    """Authorize access to the shared platform drive via a workspace.

    The platform drive is a single tree shared across every workspace; a
    workspace's members may use it only when ``platform_drive_enabled`` is
    set on the workspace row.
    """
    await require_workspace_access(user_id=user_id, workspace_id=workspace_id)
    async with AsyncSessionLocal() as db:
        registry = ServiceRegistry.instance()
        session_registry = PostgresSessionRegistry.instance()
        session_id = f"sess-{uuid4().hex}"
        session_registry.bind(session_id=session_id, db=db)
        token = session_registry.set_current_session(session_id)
        try:
            workspace = await registry.workspaces.get_workspace(workspace_id=workspace_id)
        finally:
            session_registry.reset_current_session(token)
            session_registry.unbind(session_id)

    if workspace is None or not workspace.platform_drive_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform drive is not enabled for this workspace",
        )


async def require_workspace_admin(user_id: str, workspace_id: str) -> None:
    """Authorize access to admin-only workspace capabilities.

    Used for actions that should be restricted to workspace owners and
    admins, such as inspecting the system drive (the full object storage
    tree).
    """
    await require_workspace_access(user_id=user_id, workspace_id=workspace_id)
    role = await get_workspace_role(user_id=user_id, workspace_id=workspace_id)
    if role not in ("owner", "admin"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Workspace admin role required",
        )


async def require_workspace_system_drive(user_id: str, workspace_id: str) -> None:
    """Authorize access to the system drive via a workspace.

    The system drive exposes the full object-storage tree and is gated by
    two conditions: the caller must be a workspace owner/admin AND the
    workspace must have ``system_drive_enabled`` set to true.
    """
    await require_workspace_admin(user_id=user_id, workspace_id=workspace_id)
    async with AsyncSessionLocal() as db:
        registry = ServiceRegistry.instance()
        session_registry = PostgresSessionRegistry.instance()
        session_id = f"sess-{uuid4().hex}"
        session_registry.bind(session_id=session_id, db=db)
        token = session_registry.set_current_session(session_id)
        try:
            workspace = await registry.workspaces.get_workspace(workspace_id=workspace_id)
        finally:
            session_registry.reset_current_session(token)
            session_registry.unbind(session_id)

    if workspace is None or not workspace.system_drive_enabled:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="System drive is not enabled for this workspace",
        )


__all__ = [
    "decode_token",
    "get_auth_service",
    "get_current_user",
    "get_current_user_required",
    "get_workspace_role",
    "oauth2_scheme",
    "require_workspace_access",
    "require_workspace_admin",
    "require_workspace_platform_drive",
    "require_workspace_system_drive",
    "to_user_schema",
]
