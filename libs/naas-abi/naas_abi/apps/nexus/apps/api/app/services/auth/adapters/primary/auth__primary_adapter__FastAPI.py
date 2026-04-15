"""Auth FastAPI primary adapter."""

from __future__ import annotations

import os
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.responses import Response
from fastapi.security import OAuth2PasswordRequestForm
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.services.audit import (
    log_login,
    log_logout,
    log_password_change,
    log_register,
    log_token_refresh,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service,
    get_current_user_required,
    oauth2_scheme,
    to_user_schema,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    AuthResponse,
    ForgotPasswordRequest,
    MagicLinkRequest,
    MagicLinkVerifyRequest,
    PasswordChangeRequest,
    RefreshTokenRequest,
    RefreshTokenResponse,
    ResetPasswordRequest,
    Token,
    User,
    UserCreate,
    UserLogin,
    UserUpdate,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService,
    CurrentPasswordInvalidError,
    EmailAlreadyRegisteredError,
    EmailAlreadyTakenError,
    ExpiredMagicLinkError,
    ExpiredResetTokenError,
    InvalidCredentialsError,
    InvalidMagicLinkError,
    InvalidResetTokenError,
    UserNotFoundError,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)
from naas_abi_core.services.email.EmailFactory import EmailFactory
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions as StorageExceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

router = APIRouter()

AVATAR_STORAGE_PREFIX = "nexus/avatars"
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
AVATAR_MIME_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


def _get_object_storage(request: Request) -> ObjectStorageService:
    storage = getattr(request.app.state, "object_storage", None)
    if storage is not None:
        return storage
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        module = ABIModule.get_instance()
        storage = module.engine.services.object_storage
        request.app.state.object_storage = storage
        return storage
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail="Object storage is not initialized.",
        ) from exc


@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled. Use magic link sign-in.",
        )

    identifier = get_rate_limit_identifier(request)
    await check_rate_limit(identifier, "/api/auth/register")

    try:
        user, tokens = await auth_service.register_user(
            email=user_data.email,
            password=user_data.password,
            name=user_data.name,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except EmailAlreadyRegisteredError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        ) from exc

    await log_register(user.id, request)
    return AuthResponse(
        user=to_user_schema(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled. Use magic link sign-in.",
        )

    identifier = get_rate_limit_identifier(request)
    await check_rate_limit(identifier, "/api/auth/login")

    try:
        user, tokens = await auth_service.login_user(
            email=credentials.email,
            password=credentials.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as exc:
        await log_login(
            exc.user_id,
            success=False,
            request=request,
            details={"reason": exc.reason, "email": credentials.email.lower()},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        ) from exc

    await log_login(user.id, success=True, request=request)
    return AuthResponse(
        user=to_user_schema(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        access_token = await auth_service.create_oauth_access_token(
            email=form_data.username,
            password=form_data.password,
        )
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc
    return Token(access_token=access_token)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user_required)) -> User:
    return current_user


@router.patch("/me", response_model=User)
async def update_me(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
) -> User:
    try:
        user = await auth_service.update_profile(
            user_id=current_user.id,
            name=updates.name,
            email=updates.email,
            company=updates.company,
            role=updates.role,
            bio=updates.bio,
        )
    except EmailAlreadyTakenError as exc:
        raise HTTPException(status_code=400, detail="Email already taken") from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    return to_user_schema(user)


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user_required),
    token: str | None = Depends(oauth2_scheme),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    await auth_service.logout_user(user_id=current_user.id, token=token)
    await log_logout(current_user.id, request)
    return {"status": "logged out"}


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: Request,
    token_data: RefreshTokenRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> RefreshTokenResponse:
    tokens = await auth_service.refresh_tokens(
        refresh_token=token_data.refresh_token,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )
    user = await auth_service.get_user_from_access_token(tokens.access_token)
    if user is not None:
        await log_token_refresh(user.id, request)
    return RefreshTokenResponse(
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
        )

    try:
        await auth_service.change_password(
            user_id=current_user.id,
            current_password=password_data.current_password,
            new_password=password_data.new_password,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except UserNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found") from exc
    except CurrentPasswordInvalidError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        ) from exc

    await log_password_change(current_user.id, request)
    return {
        "status": "password_changed",
        "message": "All sessions have been invalidated. Please log in again.",
    }


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
        )

    await auth_service.forgot_password(request.email)

    return {
        "status": "success",
        "message": "If an account exists with this email, you will receive a password reset link shortly.",
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
        )

    try:
        await auth_service.reset_password(token=request.token, new_password=request.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token") from exc
    except ExpiredResetTokenError as exc:
        raise HTTPException(status_code=400, detail="Reset token has expired") from exc
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc

    return {
        "status": "success",
        "message": "Password reset successfully. Please log in with your new password.",
    }


@router.post("/magic-link/request")
async def request_magic_link(
    request: Request,
    payload: MagicLinkRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    identifier = get_rate_limit_identifier(request)
    await check_rate_limit(identifier, "/api/auth/magic-link/request")

    token = await auth_service.request_magic_link(payload.email)
    if token is not None:
        await _send_magic_link_email(payload.email, token)
    return {
        "status": "success",
        "message": "If an account exists with this email, a magic sign-in link has been sent.",
    }


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    request: Request,
    payload: MagicLinkVerifyRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    try:
        user, tokens = await auth_service.verify_magic_link(
            token=payload.token,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidMagicLinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid magic link"
        ) from exc
    except ExpiredMagicLinkError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Magic link has expired"
        ) from exc

    await log_login(user.id, success=True, request=request, details={"method": "magic_link"})
    return AuthResponse(
        user=to_user_schema(user),
        access_token=tokens.access_token,
        refresh_token=tokens.refresh_token,
        expires_in=tokens.expires_in,
    )


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_AVATAR_EXTENSIONS)}",
        )

    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    unique_filename = f"{current_user.id}-{os.urandom(4).hex()}{ext}"
    object_storage.put_object(AVATAR_STORAGE_PREFIX, unique_filename, content)

    avatar_url = f"/api/auth/avatar/{unique_filename}"
    previous_avatar = current_user.avatar
    try:
        await auth_service.update_avatar(user_id=current_user.id, avatar_url=avatar_url)
    except UserNotFoundError as exc:
        try:
            object_storage.delete_object(AVATAR_STORAGE_PREFIX, unique_filename)
        except Exception:
            pass
        raise HTTPException(status_code=404, detail="User not found") from exc

    _delete_old_avatar(object_storage, previous_avatar, unique_filename)

    return {"avatar_url": avatar_url, "filename": unique_filename}


@router.get("/avatar/{filename}")
async def get_avatar(
    filename: str,
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> Response:
    ext = os.path.splitext(filename)[1].lower()
    media_type = AVATAR_MIME_TYPES.get(ext, "application/octet-stream")
    try:
        content = object_storage.get_object(AVATAR_STORAGE_PREFIX, filename)
    except StorageExceptions.ObjectNotFound:
        raise HTTPException(status_code=404, detail="Avatar not found") from None
    return Response(content=content, media_type=media_type)


@router.delete("/avatar")
async def remove_avatar(
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
    object_storage: ObjectStorageService = Depends(_get_object_storage),
) -> dict:
    previous_avatar = current_user.avatar
    try:
        await auth_service.update_avatar(user_id=current_user.id, avatar_url=None)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc

    _delete_old_avatar(object_storage, previous_avatar)

    return {"status": "ok"}


def _delete_old_avatar(
    object_storage: ObjectStorageService,
    previous_avatar: str | None,
    exclude_filename: str | None = None,
) -> None:
    if not previous_avatar or not previous_avatar.startswith("/api/auth/avatar/"):
        return
    key = previous_avatar.rsplit("/", 1)[-1]
    if key == exclude_filename:
        return
    try:
        object_storage.delete_object(AVATAR_STORAGE_PREFIX, key)
    except Exception:
        pass


async def _send_magic_link_email(to_email: str, token: str) -> None:
    if not settings.smtp_enabled:
        return

    query = urlencode({"token": token})
    magic_link_url = f"{settings.frontend_url.rstrip('/')}{settings.magic_link_path}?{query}"
    text_body = (
        "Use the link below to sign in to NEXUS:\n\n"
        f"{magic_link_url}\n\n"
        f"This link expires in {settings.magic_link_expire_minutes} minutes."
    )
    html_body = (
        "<p>Use the link below to sign in to NEXUS:</p>"
        f'<p><a href="{magic_link_url}">Sign in to NEXUS</a></p>'
        f"<p>This link expires in {settings.magic_link_expire_minutes} minutes.</p>"
    )
    email_service = EmailFactory.EmailServiceSMTP(
        host=settings.smtp_host,
        port=settings.smtp_port,
        username=settings.smtp_username,
        password=settings.smtp_password,
        use_tls=settings.smtp_use_tls,
        use_ssl=settings.smtp_use_ssl,
    )
    email_service.send(
        to_email=to_email,
        subject="Your NEXUS magic sign-in link",
        text_body=text_body,
        html_body=html_body,
        from_email=str(settings.smtp_from_email),
        from_name=settings.smtp_from_name,
    )


class AuthFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router
