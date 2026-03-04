"""
Authentication API endpoints.
Handles user registration, login, and token management.
Uses async database sessions with SQLAlchemy ORM.
Includes: refresh tokens, rate limiting, audit logging, session invalidation.
"""

import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import bcrypt
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine, get_db
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import UserModel, WorkspaceMemberModel, WorkspaceModel
from naas_abi.apps.nexus.apps.api.app.services.audit import (
    log_login,
    log_logout,
    log_password_change,
    log_register,
    log_token_refresh,
)
from naas_abi.apps.nexus.apps.api.app.services.rate_limit import (
    check_rate_limit,
    get_rate_limit_identifier,
)
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import (
    create_refresh_token,
    is_access_token_revoked,
    revoke_access_token,
    revoke_all_user_tokens,
    revoke_refresh_token,
    validate_refresh_token,
)
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()
logger = logging.getLogger(__name__)

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/token", auto_error=False)


# ============ Pydantic Schemas ============


class UserBase(BaseModel):
    """Base user model."""

    email: EmailStr
    name: str


class UserCreate(BaseModel):
    """User registration request."""

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    name: str = Field(..., min_length=1, max_length=200)


class UserLogin(BaseModel):
    """User login request."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)


class User(UserBase):
    """User model returned to client."""

    id: str
    created_at: datetime
    avatar: str | None = None
    company: str | None = None
    role: str | None = None
    bio: str | None = None


class UserInDB(User):
    """User model with hashed password (internal only)."""

    hashed_password: str


class Token(BaseModel):
    """Access token response."""

    access_token: str
    token_type: str = "bearer"


class RefreshTokenResponse(BaseModel):
    """Refresh token response."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class AuthResponse(BaseModel):
    """Authentication response with user and tokens."""

    user: User
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


# ============ Helper Functions ============


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    """Hash a password."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> tuple[str, str]:
    """
    Create a JWT access token with a unique JTI.

    Returns:
        Tuple of (token, jti)
    """
    to_encode = data.copy()
    jti = f"jti-{uuid4().hex[:16]}"
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "jti": jti})
    token = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return token, jti


def decode_token(token: str) -> dict | None:
    """Decode and validate a JWT token."""
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def _row_to_user(row: UserModel) -> User:
    """Convert an ORM UserModel to a Pydantic User."""
    return User(
        id=row.id,
        email=row.email,
        name=row.name,
        avatar=row.avatar,
        company=row.company,
        role=row.role,
        bio=row.bio,
        created_at=row.created_at,
    )


# ============ Async DB lookups ============


async def _get_user_by_id_async(db: AsyncSession, user_id: str) -> UserModel | None:
    """Look up a user by ID using async session."""
    result = await db.execute(select(UserModel).where(UserModel.id == user_id))
    return result.scalar_one_or_none()


async def _get_user_by_email_async(db: AsyncSession, email: str) -> UserModel | None:
    """Look up a user by email using async session."""
    result = await db.execute(select(UserModel).where(UserModel.email == email))
    return result.scalar_one_or_none()


# ============ Sync DB lookups (for dependency injection -- token decoding) ============
# These use the sync engine because FastAPI's Depends chain for oauth2
# doesn't easily support injecting an async session alongside the token.


async def _get_user_by_id(user_id: str) -> UserModel | None:
    """Look up a user by ID from the database (async)."""
    from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
    from sqlalchemy import text

    async with async_engine.begin() as conn:
        result = await conn.execute(
            text(
                "SELECT id, email, name, hashed_password, avatar, created_at FROM users WHERE id = :id"
            ),
            {"id": user_id},
        )
        row = result.fetchone()
        if not row:
            return None
        # Create a detached UserModel-like object
        user = UserModel(
            id=row.id,
            email=row.email,
            name=row.name,
            hashed_password=row.hashed_password,
            avatar=row.avatar,
            created_at=row.created_at,
        )
        return user


async def get_current_user(token: str = Depends(oauth2_scheme)) -> User | None:
    """Get the current authenticated user from token."""
    if not token:
        return None

    payload = decode_token(token)
    if not payload:
        return None

    user_id = payload.get("sub")
    jti = payload.get("jti")
    if not user_id:
        return None

    # Check if token has been revoked
    if jti and await is_access_token_revoked(jti):
        return None

    user_row = await _get_user_by_id(user_id)
    if not user_row:
        return None

    return _row_to_user(user_row)


async def get_current_user_required(token: str = Depends(oauth2_scheme)) -> User:
    """Get current user, raising 401 if not authenticated."""
    user = await get_current_user(token)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user


async def get_workspace_role(user_id: str, workspace_id: str) -> str | None:
    """Get user's role in a workspace. Returns None if not a member."""
    from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
    from sqlalchemy import text

    async with async_engine.connect() as conn:
        result = await conn.execute(
            text("""
                SELECT role FROM workspace_members
                WHERE workspace_id = :wid AND user_id = :uid
            """),
            {"wid": workspace_id, "uid": user_id},
        )
        row = result.fetchone()
        if not row:
            owner_result = await conn.execute(
                text("SELECT owner_id FROM workspaces WHERE id = :wid"), {"wid": workspace_id}
            )
            owner_row = owner_result.fetchone()
            if owner_row and owner_row.owner_id == user_id:
                return "owner"
            return None
        return row.role


async def require_workspace_access(user_id: str, workspace_id: str) -> str:
    """Check that user has access to a workspace. Returns the role. Raises 403 if not."""
    role = await get_workspace_role(user_id, workspace_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this workspace",
        )
    return role


# ============ Endpoints ============


@router.post("/register", response_model=AuthResponse)
async def register(
    user_data: UserCreate,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Register a new user account."""
    # Rate limiting
    identifier = get_rate_limit_identifier(request)
    await check_rate_limit(identifier, "/api/auth/register")

    email = user_data.email.lower()

    # Check if email already exists
    existing = await _get_user_by_email_async(db, email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # Create user
    user_id = str(uuid4())
    hashed_password = get_password_hash(user_data.password)
    now = datetime.now(UTC).replace(tzinfo=None)

    user_row = UserModel(
        id=user_id,
        email=email,
        name=user_data.name,
        hashed_password=hashed_password,
        created_at=now,
        updated_at=now,
    )
    db.add(user_row)

    # Create personal workspace for the user (workspace_id = user_id)
    personal_workspace = WorkspaceModel(
        id=user_id,  # Use user_id as workspace_id for personal graphs
        name=f"{user_data.name}'s Personal Workspace",
        slug=f"personal-{user_id}",  # Required field
        owner_id=user_id,
        created_at=now,
        updated_at=now,
    )
    db.add(personal_workspace)

    # Add user as workspace member
    workspace_member = WorkspaceMemberModel(
        id=f"member-{uuid4().hex[:12]}",
        workspace_id=user_id,
        user_id=user_id,
        role="owner",
        created_at=now,
    )
    db.add(workspace_member)

    await db.commit()  # Commit before creating refresh token (FK dependency)

    # Create tokens
    access_token, jti = create_access_token(data={"sub": user_id})
    refresh_token = await create_refresh_token(
        user_id=user_id,
        access_token_jti=jti,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    # Audit log
    await log_register(user_id, request)

    return AuthResponse(
        user=User(id=user_id, email=email, name=user_data.name, avatar=None, created_at=now),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    credentials: UserLogin,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> AuthResponse:
    """Login with email and password."""
    # Rate limiting
    identifier = get_rate_limit_identifier(request)
    await check_rate_limit(identifier, "/api/auth/login")

    email = credentials.email.lower()

    user_row = await _get_user_by_email_async(db, email)
    if not user_row:
        await log_login(
            None,
            success=False,
            request=request,
            details={"reason": "user_not_found", "email": email},
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    if not verify_password(credentials.password, user_row.hashed_password):
        await log_login(
            user_row.id, success=False, request=request, details={"reason": "invalid_password"}
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )

    # Create tokens
    access_token, jti = create_access_token(data={"sub": user_row.id})
    refresh_token = await create_refresh_token(
        user_id=user_row.id,
        access_token_jti=jti,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    # Audit log
    await log_login(user_row.id, success=True, request=request)

    return AuthResponse(
        user=_row_to_user(user_row),
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/token", response_model=Token)
async def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: AsyncSession = Depends(get_db),
) -> Token:
    """OAuth2 compatible token endpoint."""
    email = form_data.username.lower()

    user_row = await _get_user_by_email_async(db, email)
    if not user_row:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not verify_password(form_data.password, user_row.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token, _ = create_access_token(data={"sub": user_row.id})
    return Token(access_token=access_token)


@router.get("/me", response_model=User)
async def get_me(current_user: User = Depends(get_current_user_required)) -> User:
    """Get the current authenticated user."""
    return current_user


class UserUpdate(BaseModel):
    """Update user profile."""

    name: str | None = Field(None, min_length=1, max_length=200)
    email: str | None = Field(None, min_length=3, max_length=255)
    company: str | None = Field(None, max_length=200)
    role: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=1000)


@router.patch("/me")
async def update_me(
    updates: UserUpdate,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Update the current user's profile."""
    # Get user from database
    result = await db.execute(select(UserModel).where(UserModel.id == current_user.id))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update fields
    if updates.name is not None:
        user.name = updates.name
    if updates.email is not None:
        # Check if email is already taken
        existing = await db.execute(
            select(UserModel).where(
                (UserModel.email == updates.email) & (UserModel.id != current_user.id)
            )
        )
        if existing.scalar_one_or_none():
            raise HTTPException(status_code=400, detail="Email already taken")
        user.email = updates.email
    if updates.company is not None:
        user.company = updates.company
    if updates.role is not None:
        user.role = updates.role
    if updates.bio is not None:
        user.bio = updates.bio

    await db.commit()
    await db.refresh(user)

    # Return updated user (include avatar so clients can refresh UI)
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


@router.post("/logout")
async def logout(
    request: Request,
    current_user: User = Depends(get_current_user_required),
    token: str = Depends(oauth2_scheme),
) -> dict:
    """Logout the current user (revoke access and refresh tokens)."""
    # Decode token to get JTI and expiration
    payload = decode_token(token)
    if payload:
        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
            await revoke_access_token(jti, current_user.id, exp_datetime, reason="logout")

    # Audit log
    await log_logout(current_user.id, request)

    return {"status": "logged out"}


class RefreshTokenRequest(BaseModel):
    """Refresh token request."""

    refresh_token: str = Field(..., description="Refresh token")


@router.post("/refresh", response_model=RefreshTokenResponse)
async def refresh_access_token(
    request: Request,
    token_data: RefreshTokenRequest,
) -> RefreshTokenResponse:
    """Refresh the access token using a refresh token."""
    # Validate refresh token
    user_id = await validate_refresh_token(token_data.refresh_token)

    # Create new access token
    access_token, jti = create_access_token(data={"sub": user_id})

    # Create new refresh token (rotate)
    new_refresh_token = await create_refresh_token(
        user_id=user_id,
        access_token_jti=jti,
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
    )

    # Revoke old refresh token
    await revoke_refresh_token(token_data.refresh_token, reason="rotated")

    # Audit log
    await log_token_refresh(user_id, request)

    return RefreshTokenResponse(
        access_token=access_token,
        refresh_token=new_refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


class PasswordChangeRequest(BaseModel):
    """Password change request."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/change-password")
async def change_password(
    request: Request,
    password_data: PasswordChangeRequest,
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Change the current user's password and invalidate all sessions."""
    # Get user from database (need hashed password)
    user_row = await _get_user_by_id_async(db, current_user.id)
    if not user_row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Verify current password
    if not verify_password(password_data.current_password, user_row.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    # Hash new password
    new_hashed_password = get_password_hash(password_data.new_password)

    # Update password
    user_row.hashed_password = new_hashed_password
    user_row.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()

    # Revoke all refresh tokens (invalidate all sessions)
    await revoke_all_user_tokens(current_user.id, reason="password_change")

    # Log password change
    now = datetime.now(UTC).replace(tzinfo=None)
    async with async_engine.begin() as conn:
        from sqlalchemy import text

        pw_change_id = f"pwc-{uuid4().hex[:12]}"
        await conn.execute(
            text("""
                INSERT INTO password_changes (id, user_id, changed_at, ip_address, user_agent)
                VALUES (:id, :user_id, :changed_at, :ip_address, :user_agent)
            """),
            {
                "id": pw_change_id,
                "user_id": current_user.id,
                "changed_at": now,
                "ip_address": request.client.host if request.client else None,
                "user_agent": request.headers.get("user-agent"),
            },
        )

    # Audit log
    await log_password_change(current_user.id, request)

    return {
        "status": "password_changed",
        "message": "All sessions have been invalidated. Please log in again.",
    }


# ============================================
# Password Reset Flow
# ============================================


class ForgotPasswordRequest(BaseModel):
    """Request password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Reset password with token."""

    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/forgot-password")
async def forgot_password(
    request: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Request password reset link. Sends email with reset token.
    Always returns success (don't reveal if email exists).
    """
    import secrets

    from naas_abi.apps.nexus.apps.api.app.models import PasswordResetTokenModel

    # Find user by email
    result = await db.execute(select(UserModel).where(UserModel.email == request.email))
    user = result.scalar_one_or_none()

    if user:
        # Generate secure token
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(UTC) + timedelta(hours=1)
        expires_at = expires_at.replace(tzinfo=None)

        # Invalidate any existing unused tokens for this user
        await db.execute(
            select(PasswordResetTokenModel).where(
                (PasswordResetTokenModel.user_id == user.id)
                & (PasswordResetTokenModel.used.is_(False))
            )
        )
        existing_tokens = (
            (
                await db.execute(
                    select(PasswordResetTokenModel).where(
                        (PasswordResetTokenModel.user_id == user.id)
                        & (PasswordResetTokenModel.used.is_(False))
                    )
                )
            )
            .scalars()
            .all()
        )

        for old_token in existing_tokens:
            old_token.used = True

        # Create new token
        reset_token = PasswordResetTokenModel(
            id=str(uuid4()),
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            used=False,
            created_at=datetime.now(UTC).replace(tzinfo=None),
        )
        db.add(reset_token)
        await db.flush()

        # TODO: Send email with reset link
        # For now, just log it (in production, send via email service)
        reset_link = f"http://localhost:3000/auth/reset-password?token={token}"
        logger.info(f"Password reset link for {user.email}: {reset_link}")

    # Always return success (security best practice - don't reveal if email exists)
    return {
        "status": "success",
        "message": "If an account exists with this email, you will receive a password reset link shortly.",
    }


@router.post("/reset-password")
async def reset_password(
    request: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Reset password using token from email."""
    from naas_abi.apps.nexus.apps.api.app.models import PasswordResetTokenModel

    # Find valid token
    result = await db.execute(
        select(PasswordResetTokenModel).where(
            (PasswordResetTokenModel.token == request.token)
            & (PasswordResetTokenModel.used.is_(False))
        )
    )
    reset_token = result.scalar_one_or_none()

    if not reset_token:
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    # Check if expired
    now = datetime.now(UTC).replace(tzinfo=None)
    if reset_token.expires_at < now:
        raise HTTPException(status_code=400, detail="Reset token has expired")

    # Get user
    user_result = await db.execute(select(UserModel).where(UserModel.id == reset_token.user_id))
    user = user_result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    # Update password
    user.hashed_password = get_password_hash(request.new_password)

    # Mark token as used
    reset_token.used = True

    # Invalidate all refresh tokens (force re-login everywhere)
    await revoke_all_user_tokens(user.id)

    await db.flush()

    return {
        "status": "success",
        "message": "Password reset successfully. Please log in with your new password.",
    }


# Avatar upload
AVATAR_DIR = Path("uploads/avatars")
AVATAR_DIR.mkdir(parents=True, exist_ok=True)
ALLOWED_AVATAR_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".webp"}
MAX_AVATAR_SIZE = 2 * 1024 * 1024  # 2MB


@router.post("/upload-avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a profile avatar for the authenticated user."""
    # Validate file type
    if not file.filename:
        raise HTTPException(status_code=400, detail="No filename provided")

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_AVATAR_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid file type. Allowed: {', '.join(ALLOWED_AVATAR_EXTENSIONS)}",
        )

    # Check file size
    content = await file.read()
    if len(content) > MAX_AVATAR_SIZE:
        raise HTTPException(status_code=400, detail="File too large (max 2MB)")

    # Generate unique filename
    unique_filename = f"{current_user.id}-{uuid4().hex[:8]}{ext}"
    file_path = AVATAR_DIR / unique_filename

    # Save file
    with open(file_path, "wb") as f:
        f.write(content)

    # Generate URL
    avatar_url = f"/uploads/avatars/{unique_filename}"

    # Update user
    result = await db.execute(select(UserModel).where(UserModel.id == current_user.id))
    user = result.scalar_one_or_none()
    if not user:
        # Clean up uploaded file
        file_path.unlink(missing_ok=True)
        raise HTTPException(status_code=404, detail="User not found")

    # Delete old avatar file if it exists and is a local upload
    if user.avatar and user.avatar.startswith("/uploads/avatars/"):
        old_file = AVATAR_DIR / os.path.basename(user.avatar)
        old_file.unlink(missing_ok=True)

    user.avatar = avatar_url
    user.updated_at = datetime.now(UTC).replace(tzinfo=None)
    await db.commit()
    await db.refresh(user)

    return {
        "avatar_url": avatar_url,
        "filename": unique_filename,
    }
