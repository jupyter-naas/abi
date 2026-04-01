"""Auth FastAPI primary adapter."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import (APIRouter, Depends, File, HTTPException, Request,
                     UploadFile, status)
from fastapi.security import OAuth2PasswordRequestForm
from naas_abi.apps.nexus.apps.api.app.services.audit import (
    log_login, log_logout, log_password_change, log_register,
    log_token_refresh)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (
    get_auth_service, get_current_user_required, oauth2_scheme, to_user_schema)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (
    AuthResponse, ForgotPasswordRequest, PasswordChangeRequest,
    RefreshTokenRequest, RefreshTokenResponse, ResetPasswordRequest, Token,
    User, UserCreate, UserLogin, UserUpdate)
from naas_abi.apps.nexus.apps.api.app.services.auth.service import (
    AuthService, CurrentPasswordInvalidError, EmailAlreadyRegisteredError,
    EmailAlreadyTakenError, ExpiredResetTokenError, InvalidCredentialsError,
    InvalidResetTokenError, UserNotFoundError)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit, get_rate_limit_identifier)

router = APIRouter()
logger = logging.getLogger(__name__)

# Anchor to the api package root (same tree used by _mount_static_assets in main.py)
# main.py uses: Path(__file__).parent.parent / "uploads"
# This file lives at: .../apps/api/app/services/auth/adapters/primary/
# Six parents up reaches .../apps/api/
AVATAR_DIR = Path(__file__).parents[5] / "uploads" / "avatars"
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024


@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    auth_service: AuthService = Depends(get_auth_service),
) -> AuthResponse:
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
    token = await auth_service.forgot_password(request.email)
    if token:
        reset_link = f"http://localhost:3000/auth/reset-password?token={token}"
        logger.info("Password reset link for %s: %s", request.email, reset_link)

    return {
        "status": "success",
        "message": "If an account exists with this email, you will receive a password reset link shortly.",
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
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


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
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
    file_path = AVATAR_DIR / unique_filename
    with open(file_path, "wb") as f:
        f.write(content)

    avatar_url = f"/uploads/avatars/{unique_filename}"
    previous_avatar = current_user.avatar
    try:
        await auth_service.update_avatar(user_id=current_user.id, avatar_url=avatar_url)
    except UserNotFoundError as exc:
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="User not found") from exc

    if previous_avatar and previous_avatar.startswith("/uploads/avatars/"):
        old_file = AVATAR_DIR / os.path.basename(previous_avatar)
        if old_file.name != unique_filename:
            old_file.unlink(missing_ok=True)

    return {"avatar_url": avatar_url, "filename": unique_filename}


@router.delete("/avatar")
async def remove_avatar(
    current_user: User = Depends(get_current_user_required),
    auth_service: AuthService = Depends(get_auth_service),
) -> dict:
    previous_avatar = current_user.avatar
    try:
        await auth_service.update_avatar(user_id=current_user.id, avatar_url=None)
    except UserNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc

    if previous_avatar and previous_avatar.startswith("/uploads/avatars/"):
        old_file = AVATAR_DIR / os.path.basename(previous_avatar)
        old_file.unlink(missing_ok=True)

    return {"status": "ok"}


class AuthFastAPIPrimaryAdapter:
    def __init__(self) -> None:
        self.router = router
