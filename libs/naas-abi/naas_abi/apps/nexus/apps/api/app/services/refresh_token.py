"""
Refresh Token Service
Manages long-lived refresh tokens for secure token rotation.
Uses async database operations to avoid locking.
"""

import hashlib
import secrets
from datetime import datetime, timedelta
from uuid import uuid4

from fastapi import HTTPException, status
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from sqlalchemy import text


def generate_refresh_token() -> str:
    """Generate a cryptographically secure refresh token."""
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    """Hash a token for storage (SHA-256)."""
    return hashlib.sha256(token.encode()).hexdigest()


async def create_refresh_token(
    user_id: str,
    access_token_jti: str | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> str:
    """
    Create a new refresh token for a user.

    Args:
        user_id: User ID
        access_token_jti: JTI of the associated access token
        user_agent: User agent string
        ip_address: IP address

    Returns:
        The refresh token (plaintext, return to client)
    """
    token = generate_refresh_token()
    token_hash = hash_token(token)
    token_id = f"rt-{uuid4().hex[:12]}"
    now = datetime.now(UTC).replace(tzinfo=None)
    expires_at = datetime.now(UTC).replace(tzinfo=None) + timedelta(days=settings.refresh_token_expire_days)

    async with async_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO refresh_tokens
                (id, user_id, token_hash, access_token_jti, expires_at, created_at, user_agent, ip_address)
                VALUES
                (:id, :user_id, :token_hash, :access_token_jti, :expires_at, :created_at, :user_agent, :ip_address)
            """),
            {
                "id": token_id,
                "user_id": user_id,
                "token_hash": token_hash,
                "access_token_jti": access_token_jti,
                "expires_at": expires_at,
                "created_at": now,
                "user_agent": user_agent,
                "ip_address": ip_address,
            },
        )

    return token


async def validate_refresh_token(token: str) -> str:
    """
    Validate a refresh token and return the user_id.

    Args:
        token: The refresh token

    Returns:
        The user_id

    Raises:
        HTTPException: If token is invalid, expired, or revoked
    """
    token_hash = hash_token(token)
    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_engine.begin() as conn:
        result = await conn.execute(
            text("""
                SELECT user_id, expires_at, revoked_at
                FROM refresh_tokens
                WHERE token_hash = :token_hash
            """),
            {"token_hash": token_hash},
        )
        row = result.fetchone()

        if not row:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        if row.revoked_at:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has been revoked",
            )

        if row.expires_at < now:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired",
            )

        # Update last_used_at
        await conn.execute(
            text("""
                UPDATE refresh_tokens
                SET last_used_at = :now
                WHERE token_hash = :token_hash
            """),
            {"now": now, "token_hash": token_hash},
        )

        return row.user_id


async def revoke_refresh_token(token: str, reason: str = "user_requested") -> None:
    """
    Revoke a refresh token.

    Args:
        token: The refresh token
        reason: Reason for revocation
    """
    token_hash = hash_token(token)
    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_engine.begin() as conn:
        await conn.execute(
            text("""
                UPDATE refresh_tokens
                SET revoked_at = :now, revoked_reason = :reason
                WHERE token_hash = :token_hash
            """),
            {"now": now, "reason": reason, "token_hash": token_hash},
        )


async def revoke_all_user_tokens(user_id: str, reason: str = "password_change") -> None:
    """
    Revoke all refresh tokens for a user (e.g., on password change).

    Args:
        user_id: User ID
        reason: Reason for revocation
    """
    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_engine.begin() as conn:
        await conn.execute(
            text("""
                UPDATE refresh_tokens
                SET revoked_at = :now, revoked_reason = :reason
                WHERE user_id = :user_id AND revoked_at IS NULL
            """),
            {"now": now, "reason": reason, "user_id": user_id},
        )


async def revoke_access_token(jti: str, user_id: str, expires_at: datetime, reason: str = "logout") -> None:
    """
    Revoke an access token immediately (add to blacklist).

    Args:
        jti: JWT ID
        user_id: User ID
        expires_at: Token expiration time
        reason: Reason for revocation
    """
    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_engine.begin() as conn:
        await conn.execute(
            text("""
                INSERT INTO revoked_tokens (jti, user_id, revoked_at, revoked_reason, expires_at)
                VALUES (:jti, :user_id, :revoked_at, :reason, :expires_at)
            """),
            {
                "jti": jti,
                "user_id": user_id,
                "revoked_at": now,
                "reason": reason,
                "expires_at": expires_at,
            },
        )


async def is_access_token_revoked(jti: str) -> bool:
    """Check if an access token has been revoked."""
    from naas_abi.apps.nexus.apps.api.app.core.database import async_engine
    async with async_engine.begin() as conn:
        result = await conn.execute(
            text("SELECT 1 FROM revoked_tokens WHERE jti = :jti"),
            {"jti": jti},
        )
        return result.fetchone() is not None


async def cleanup_expired_tokens() -> None:
    """Clean up expired refresh tokens and revoked access tokens (background task)."""
    now = datetime.now(UTC).replace(tzinfo=None)

    async with async_engine.begin() as conn:
        # Delete expired refresh tokens
        await conn.execute(
            text("DELETE FROM refresh_tokens WHERE expires_at < :now"),
            {"now": now},
        )
        # Delete expired revoked access tokens
        await conn.execute(
            text("DELETE FROM revoked_tokens WHERE expires_at < :now"),
            {"now": now},
        )
