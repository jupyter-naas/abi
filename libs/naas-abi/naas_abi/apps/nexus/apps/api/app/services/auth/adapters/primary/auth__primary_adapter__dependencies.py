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


__all__ = [
    "decode_token",
    "get_auth_service",
    "get_current_user",
    "get_current_user_required",
    "get_workspace_role",
    "oauth2_scheme",
    "require_workspace_access",
    "to_user_schema",
]
