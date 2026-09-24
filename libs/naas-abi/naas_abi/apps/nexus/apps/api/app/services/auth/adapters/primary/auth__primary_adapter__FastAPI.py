"""Auth FastAPI primary adapter."""

from __future__ import annotations

import logging
import os

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
    OtpVerifyRequest,
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
    DefaultPasswordNotAllowedError,
    EmailAlreadyRegisteredError,
    EmailAlreadyTakenError,
    ExpiredMagicLinkError,
    ExpiredOtpError,
    ExpiredResetTokenError,
    InvalidCredentialsError,
    InvalidMagicLinkError,
    InvalidOtpError,
    InvalidResetTokenError,
    SignupDisabledError,
    UserNotFoundError,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    ensure_under_limit,
    get_rate_limit_identifier,
    record_attempt,
)
from naas_abi_core.services.email.EmailService import EmailService
from naas_abi_core.services.object_storage.ObjectStoragePort import Exceptions as StorageExceptions
from naas_abi_core.services.object_storage.ObjectStorageService import ObjectStorageService

logger = logging.getLogger(__name__)

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


def _get_email_service(request: Request) -> EmailService | None:
    """Resolve the engine-configured email service.

    Returns None if no adapter is wired — caller logs the message instead of
    sending it (useful for local dev without SMTP).
    """
    service = getattr(request.app.state, "email_service", None)
    if service is not None:
        return service
    try:
        from naas_abi import ABIModule  # noqa: PLC0415

        service = ABIModule.get_instance().engine.services.email
        request.app.state.email_service = service
        return service
    except Exception:
        return None


_DEFAULT_PASSWORD_DETAIL = "This password is a published default and cannot be used."


def _limit_keys(request: Request, account: str | None) -> list[tuple[str, int]]:
    """(identifier, limit) pairs: the client IP, plus the account when known."""
    keys = [(get_rate_limit_identifier(request), settings.rate_limit_ip_attempts)]
    if account:
        keys.append((f"email:{account.strip().lower()}", settings.rate_limit_login_attempts))
    return keys


async def _refuse_if_limited(request: Request, endpoint: str, account: str | None = None) -> None:
    for identifier, limit in _limit_keys(request, account):
        await ensure_under_limit(identifier, endpoint, limit)


async def _count_attempt(request: Request, endpoint: str, account: str | None = None) -> None:
    for identifier, _limit in _limit_keys(request, account):
        await record_attempt(identifier, endpoint)


@router.get("/config", response_model=dict[str, bool | int])
async def get_auth_config() -> dict[str, bool | int]:
    return {
        "password_auth_enabled": settings.auth_password_enabled,
        "signup_enabled": settings.auth_password_enabled and settings.auth_signup_enabled,
        "otp_auth_enabled": True,
        "otp_code_length": settings.otp_code_length,
    }


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

    await _refuse_if_limited(request, "/api/auth/register")
    await _count_attempt(request, "/api/auth/register")

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
    except DefaultPasswordNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=_DEFAULT_PASSWORD_DETAIL) from exc
    except SignupDisabledError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Registration is disabled. Ask an administrator for an invitation.",
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

    await _refuse_if_limited(request, "/api/auth/login", credentials.email)

    try:
        user, tokens = await auth_service.login_user(
            email=credentials.email,
            password=credentials.password,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidCredentialsError as exc:
        await _count_attempt(request, "/api/auth/login", credentials.email)
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
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    auth_service: AuthService = Depends(get_auth_service),
) -> Token:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    await _refuse_if_limited(request, "/api/auth/token", form_data.username)
    try:
        access_token = await auth_service.create_oauth_access_token(
            email=form_data.username,
            password=form_data.password,
        )
    except InvalidCredentialsError as exc:
        await _count_attempt(request, "/api/auth/token", form_data.username)
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
    except DefaultPasswordNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=_DEFAULT_PASSWORD_DETAIL) from exc

    await log_password_change(current_user.id, request)
    return {
        "status": "password_changed",
        "message": "All sessions have been invalidated. Please log in again.",
    }


@router.post("/forgot-password")
async def forgot_password(
    request: Request,
    payload: ForgotPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
        )

    await _refuse_if_limited(request, "/api/auth/forgot-password")
    await _count_attempt(request, "/api/auth/forgot-password")
    await auth_service.forgot_password(payload.email)

    return {
        "status": "success",
        "message": "If an account exists with this email, you will receive a password reset link shortly.",
    }


@router.post("/reset-password")
async def reset_password(
    request: Request,
    payload: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    if not settings.auth_password_enabled:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Password authentication is disabled.",
        )

    await _refuse_if_limited(request, "/api/auth/reset-password")
    await _count_attempt(request, "/api/auth/reset-password")
    try:
        await auth_service.reset_password(token=payload.token, new_password=payload.new_password)
    except InvalidResetTokenError as exc:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token") from exc
    except ExpiredResetTokenError as exc:
        raise HTTPException(status_code=400, detail="Reset token has expired") from exc
    except DefaultPasswordNotAllowedError as exc:
        raise HTTPException(status_code=400, detail=_DEFAULT_PASSWORD_DETAIL) from exc
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
    email_service: EmailService | None = Depends(_get_email_service),
) -> dict:
    # Every request counts: each one mints a code, so an attacker must not be
    # able to farm fresh codes for one account.
    await _refuse_if_limited(request, "/api/auth/magic-link/request", payload.email)
    await _count_attempt(request, "/api/auth/magic-link/request", payload.email)

    challenge = await auth_service.request_magic_link(payload.email)
    if challenge is not None:
        try:
            await _send_magic_link_email(
                payload.email,
                challenge.token,
                challenge.otp_code,
                email_service,
            )
        except Exception:
            # Challenge is committed before send. Revoke orphans so a later
            # unused row cannot shadow the OTP the user actually received.
            await auth_service.invalidate_magic_link_challenge(challenge.token_id)
            raise
    return {
        "status": "success",
        "message": (
            "If an account exists with this email, a sign-in code has been sent. "
            "You can also use the magic link in the email."
        ),
    }


@router.post("/magic-link/verify", response_model=AuthResponse)
async def verify_magic_link(
    request: Request,
    payload: MagicLinkVerifyRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    await _refuse_if_limited(request, "/api/auth/magic-link/verify")
    await _count_attempt(request, "/api/auth/magic-link/verify")
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


@router.post("/otp/verify", response_model=AuthResponse)
async def verify_otp(
    request: Request,
    payload: OtpVerifyRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
    # Bounded per IP and per email so a distributed attacker cannot spray codes.
    await _refuse_if_limited(request, "/api/auth/otp/verify", payload.email)

    try:
        user, tokens = await auth_service.verify_otp(
            email=payload.email,
            code=payload.code,
            user_agent=request.headers.get("user-agent"),
            ip_address=request.client.host if request.client else None,
        )
    except InvalidOtpError as exc:
        await _count_attempt(request, "/api/auth/otp/verify", payload.email)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired sign-in code",
        ) from exc
    except ExpiredOtpError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Sign-in code has expired",
        ) from exc

    await log_login(user.id, success=True, request=request, details={"method": "email_otp"})
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


async def _send_magic_link_email(
    to_email: str,
    token: str,
    otp_code: str,
    email_service: EmailService | None,
) -> None:
    from naas_abi.apps.nexus.apps.api.app.services.invites.sign_in_email import (
        magic_link_url_for_token,
        render_sign_in_email,
    )

    magic_link_url = magic_link_url_for_token(token)

    if email_service is None:
        if settings.log_otp_codes_when_email_unavailable:
            logger.info(
                "Email service unavailable. Sign-in code for %s: %s (link: %s)",
                to_email,
                otp_code,
                magic_link_url,
            )
        else:
            logger.info(
                "Email service unavailable for %s; OTP not logged "
                "(set log_otp_codes_when_email_unavailable=true for local debug)",
                to_email,
            )
        return

    subject, text_body, html_body, attachments = render_sign_in_email(
        magic_link_url=magic_link_url,
        otp_code=otp_code,
    )
    email_service.send(
        to_email=to_email,
        subject=subject,
        text_body=text_body,
        html_body=html_body,
        from_email=str(settings.email_from_address),
        from_name=settings.email_from_name,
        attachments=attachments or None,
    )


class AuthFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router
