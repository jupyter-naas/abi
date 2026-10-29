from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
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
from naas_abi_core.apps.api.abi_api_key_auth import is_abi_api_token_valid
from sqlalchemy.ext.asyncio import AsyncSession

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


def to_user_schema(user: AuthUserRecord) -> User:
    return User(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar=user.avatar,
        organization=user.organization,
        job_title=user.job_title,
        bio=user.bio,
        linkedin_url=user.linkedin_url,
        github_handle=user.github_handle,
        is_superadmin=user.is_superadmin,
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


async def get_current_user_released(token: str | None = Depends(oauth2_scheme)) -> User:
    """``get_current_user_required`` on its own short-lived session.

    The request does not keep a pooled connection while it runs. Use it on hot
    read paths that fire many requests at once (Maps layer data, logos): with
    the request-scoped session, every waiting request holds a connection and
    the pool runs dry.
    """
    async with AsyncSessionLocal() as db:
        user = await AuthService(
            adapter=AuthSecondaryAdapterPostgres(db=db)
        ).get_user_from_access_token(token)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return to_user_schema(user)


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


async def require_superadmin(
    current_user: User = Depends(get_current_user_required),
) -> User:
    """Authorize platform-level admin access.

    The ``is_superadmin`` flag is set on the user record: managed in Admin >
    Users, and promoted on boot for operators listed in config ``users``.
    Used for cross-workspace diagnostic surfaces like the live platform event
    stream.
    """
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform superadmin role required",
        )
    return current_user


@dataclass(frozen=True)
class PlatformCaller:
    """Who called a route open to super admins and to scripts with ``ABI_API_KEY``.

    ``via`` is how they authenticated; an API key has no user."""

    via: Literal["user", "api_key"]
    user: User | None = None

    @property
    def user_id(self) -> str:
        return self.user.id if self.user else ""


async def require_superadmin_or_api_key(
    token: str | None = Depends(oauth2_scheme),
    current_user: User | None = Depends(get_current_user),
) -> PlatformCaller:
    """Authorize platform-level admin access for a super admin or a script.

    ``Authorization: Bearer <ABI_API_KEY>`` is the instance's shared key and
    stands for the operator: it reaches everything a super admin does on the
    routes that use this dependency (never a query parameter or a cookie, which
    would put the key in logs). Otherwise it is ``require_superadmin``: 401
    without a session, 403 for a user who is not a super admin.
    """
    if is_abi_api_token_valid(token):
        return PlatformCaller("api_key")
    if current_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not current_user.is_superadmin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Platform superadmin role required",
        )
    return PlatformCaller("user", current_user)


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
    "PlatformCaller",
    "require_superadmin_or_api_key",
    "require_workspace_access",
    "require_workspace_admin",
    "require_workspace_platform_drive",
    "require_workspace_system_drive",
    "to_user_schema",
]
