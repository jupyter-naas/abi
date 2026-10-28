from __future__ import annotations

from uuid import uuid4

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
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
from naas_abi.apps.nexus.apps.api.app.services.auth.credentials import (
    Credential,
    accepted_kinds,
    bearer_credential,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.auth.service import AuthService
from naas_abi.apps.nexus.apps.api.app.services.iam import authz as authz_module
from naas_abi.apps.nexus.apps.api.app.services.iam.runtime import IAMUnavailableError
from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry
from naas_abi.apps.nexus.apps.api.app.services.workspaces import WorkspacePermissionError
from sqlalchemy.ext.asyncio import AsyncSession

_bearer = HTTPBearer(
    auto_error=False,
    scheme_name="ApiKey",
    description="A personal API key (abi_pk_...). The web app signs in with a cookie.",
)


async def bearer_token(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> str | None:
    """The bearer token of the request, if any (``credentials.py`` says what it is)."""
    return credentials.credentials if credentials is not None else None


def to_user_schema(user: AuthUserRecord, *, is_superadmin: bool | None = None) -> User:
    """``is_superadmin`` is IAM's (``builtin.platform_admin``), never the stored flag."""
    return User(
        id=user.id,
        email=user.email,
        name=user.name,
        avatar=user.avatar,
        organization=user.organization,
        job_title=user.job_title,
        bio=user.bio,
        is_superadmin=bool(is_superadmin),
        created_at=user.created_at,
    )


def get_auth_service(db: AsyncSession = Depends(get_db)) -> AuthService:
    return AuthService(adapter=AuthSecondaryAdapterPostgres(db=db))


async def request_credential(request: Request, token: str | None) -> Credential | None:
    """The credential of this request, as ``RequestIdentityMiddleware`` resolved
    it (it leaves the answer on ``request.state``); resolved here when the
    middleware did not run, from the bearer token, for the kinds this route
    takes."""
    state = request.state
    credential = getattr(state, "nexus_credential", None)
    if credential is not None:
        return credential
    if getattr(state, "nexus_credential_refused", None) is not None:
        return None
    if token:
        found = await bearer_credential(token)
        if found is not None and found.kind in accepted_kinds(request.url.path):
            return found
        if found is not None:
            state.nexus_credential_refused = found.kind
    return None


async def get_current_user(
    request: Request,
    token: str | None = Depends(bearer_token),
    auth_service: AuthService = Depends(get_auth_service),
) -> User | None:
    """The user of the request's credential: a session (the bearer token, else
    the session cookie, as ``RequestIdentityMiddleware`` resolved it), or the API
    key or coding key the route takes (``services/auth/credentials.py``)."""
    credential = await request_credential(request, token)
    if credential is None:
        return None
    user = await auth_service.adapter.get_user_by_id(credential.user_id)
    if user is None:
        return None
    # ``is_superadmin`` is not asked here: an authorization round trip on every
    # request, for a flag few routes read. ``to_signed_in_user`` asks for it.
    return to_user_schema(user)


async def to_signed_in_user(user: AuthUserRecord) -> User:
    """The user as the account's own routes show them: with ``is_superadmin``, asked
    of IAM when the answer is wanted (a profile, a session, a sign-in)."""
    return to_user_schema(user, is_superadmin=await is_platform_admin(user.id))


async def with_platform_role(user: User) -> User:
    """``user`` with ``is_superadmin`` asked of IAM (see ``to_signed_in_user``)."""
    return user.model_copy(update={"is_superadmin": await is_platform_admin(user.id)})


def _refuse(request: Request) -> HTTPException:
    """Why the request has no user: a failed CSRF check, a credential of a kind
    this route does not take, or none."""
    if getattr(request.state, "nexus_csrf_failed", False):
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="CSRF token missing or invalid",
        )
    refused = getattr(request.state, "nexus_credential_refused", None)
    if refused is not None:
        # A real credential, of a kind this route does not take: a key on
        # the account, a coding agent's key anywhere but the gateway.
        return HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"A {refused} credential cannot be used here",
        )
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_required(
    request: Request, current_user: User | None = Depends(get_current_user)
) -> User:
    if not current_user:
        raise _refuse(request)
    return current_user


async def get_current_user_released(
    request: Request, token: str | None = Depends(bearer_token)
) -> User:
    """``get_current_user_required`` on its own short-lived session.

    The request does not keep a pooled connection while it runs. Use it on hot
    read paths that fire many requests at once (Maps layer data, logos): with
    the request-scoped session, every waiting request holds a connection and
    the pool runs dry.
    """
    credential = await request_credential(request, token)
    user = None
    if credential is not None:
        async with AsyncSessionLocal() as db:
            user = await AuthSecondaryAdapterPostgres(db=db).get_user_by_id(credential.user_id)
    if user is None:
        raise _refuse(request)
    return to_user_schema(user)


async def is_platform_admin(user_id: str) -> bool:
    """Whether IAM holds the user as a platform admin: they may manage the
    system (``nexus:ManageSystem``, which no workspace or org role reaches)."""
    try:
        return await authz_module.AUTHZ.allowed("ManageSystem", user=user_id)
    except IAMUnavailableError:
        return False  # no IAM, no platform admin; any other failure surfaces


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


async def require_superadmin(
    request: Request,
    current_user: User = Depends(get_current_user_required),
) -> User:
    """Authorize platform-level admin access through IAM.

    ``nexus:ReadSystem`` for a read, ``nexus:ManageSystem`` for anything else:
    held by ``builtin.platform_admin`` alone (the ``users[].is_superadmin`` of
    the configuration is its attachment).
    """
    action = "ReadSystem" if request.method in ("GET", "HEAD", "OPTIONS") else "ManageSystem"
    try:
        await authz_module.AUTHZ.require(
            action, user=current_user, denied="Platform superadmin role required"
        )
    except authz_module.AuthzDenied as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="Platform superadmin role required"
        ) from exc
    return current_user


__all__ = [
    "bearer_token",
    "get_workspace_role",
    "is_platform_admin",
    "require_superadmin",
    "require_workspace_access",
    "get_auth_service",
    "get_current_user",
    "get_current_user_required",
    "get_current_user_released",
    "to_signed_in_user",
    "with_platform_role",
    "to_user_schema",
]
