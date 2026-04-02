from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import uuid4

import bcrypt
from jose import JWTError, jwt
from naas_abi.apps.nexus.apps.api.app.core.config import settings
from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.auth.port import AuthPersistencePort, AuthUserRecord
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import (
    create_refresh_token,
    is_access_token_revoked,
    revoke_access_token,
    revoke_all_user_tokens,
    revoke_refresh_token,
    validate_refresh_token,
)


@dataclass
class AuthTokens:
    access_token: str
    refresh_token: str
    expires_in: int


@dataclass
class EmailAlreadyRegisteredError(ValueError):
    def __str__(self) -> str:
        return "email_already_registered"


@dataclass
class EmailAlreadyTakenError(ValueError):
    def __str__(self) -> str:
        return "email_already_taken"


@dataclass
class UserNotFoundError(ValueError):
    user_id: str | None = None

    def __str__(self) -> str:
        return "user_not_found"


@dataclass
class InvalidCredentialsError(ValueError):
    reason: str
    user_id: str | None = None

    def __str__(self) -> str:
        return "invalid_credentials"


@dataclass
class CurrentPasswordInvalidError(ValueError):
    def __str__(self) -> str:
        return "current_password_invalid"


@dataclass
class InvalidResetTokenError(ValueError):
    def __str__(self) -> str:
        return "invalid_reset_token"


@dataclass
class ExpiredResetTokenError(ValueError):
    def __str__(self) -> str:
        return "expired_reset_token"


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def create_access_token(data: dict, expires_delta: timedelta | None = None) -> tuple[str, str]:
    to_encode = data.copy()
    jti = f"jti-{uuid4().hex[:16]}"
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "jti": jti})
    token = jwt.encode(to_encode, settings.secret_key, algorithm="HS256")
    return token, jti


def decode_token(token: str) -> dict | None:
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        return payload
    except JWTError:
        return None


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthService:
    def __init__(self, adapter: AuthPersistencePort):
        self.adapter = adapter

    async def register_user(
        self,
        email: str,
        password: str,
        name: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[AuthUserRecord, AuthTokens]:
        normalized_email = email.lower()
        if await self.adapter.user_exists_with_email(normalized_email):
            raise EmailAlreadyRegisteredError()

        user_id = str(uuid4())
        user = await self.adapter.create_user_with_personal_workspace(
            user_id=user_id,
            email=normalized_email,
            name=name,
            hashed_password=get_password_hash(password),
            now=now_utc_naive(),
        )
        await self.adapter.commit()

        access_token, jti = create_access_token(data={"sub": user_id})
        refresh_token = await create_refresh_token(
            user_id=user_id,
            access_token_jti=jti,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return (
            user,
            AuthTokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_expire_minutes * 60,
            ),
        )

    async def login_user(
        self,
        email: str,
        password: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> tuple[AuthUserRecord, AuthTokens]:
        normalized_email = email.lower()
        user = await self.adapter.get_user_by_email(normalized_email)
        if user is None:
            raise InvalidCredentialsError(reason="user_not_found")

        if not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(reason="invalid_password", user_id=user.id)

        access_token, jti = create_access_token(data={"sub": user.id})
        refresh_token = await create_refresh_token(
            user_id=user.id,
            access_token_jti=jti,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        return (
            user,
            AuthTokens(
                access_token=access_token,
                refresh_token=refresh_token,
                expires_in=settings.access_token_expire_minutes * 60,
            ),
        )

    async def create_oauth_access_token(self, email: str, password: str) -> str:
        user = await self.adapter.get_user_by_email(email.lower())
        if user is None or not verify_password(password, user.hashed_password):
            raise InvalidCredentialsError(reason="invalid_credentials")
        access_token, _ = create_access_token(data={"sub": user.id})
        return access_token

    async def get_user_from_access_token(self, token: str | None) -> AuthUserRecord | None:
        if not token:
            return None
        payload = decode_token(token)
        if not payload:
            return None

        user_id = payload.get("sub")
        jti = payload.get("jti")
        if not user_id:
            return None
        if jti and await is_access_token_revoked(jti):
            return None
        return await self.adapter.get_user_by_id(user_id)

    async def update_profile(
        self,
        user_id: str,
        name: str | None,
        email: str | None,
        company: str | None,
        role: str | None,
        bio: str | None,
    ) -> AuthUserRecord:
        normalized_email = email.lower() if email is not None else None
        if normalized_email and await self.adapter.user_exists_with_email(
            normalized_email,
            exclude_user_id=user_id,
        ):
            raise EmailAlreadyTakenError()

        updated_user = await self.adapter.update_user_profile(
            user_id=user_id,
            name=name,
            email=normalized_email,
            company=company,
            role=role,
            bio=bio,
        )
        if updated_user is None:
            raise UserNotFoundError(user_id=user_id)

        await self.adapter.commit()
        return updated_user

    async def logout_user(self, user_id: str, token: str | None) -> None:
        if not token:
            return
        payload = decode_token(token)
        if not payload:
            return

        jti = payload.get("jti")
        exp = payload.get("exp")
        if jti and exp:
            exp_datetime = datetime.fromtimestamp(exp, tz=UTC)
            await revoke_access_token(jti, user_id, exp_datetime, reason="logout")

    async def refresh_tokens(
        self,
        refresh_token: str,
        user_agent: str | None,
        ip_address: str | None,
    ) -> AuthTokens:
        user_id = await validate_refresh_token(refresh_token)
        access_token, jti = create_access_token(data={"sub": user_id})
        new_refresh_token = await create_refresh_token(
            user_id=user_id,
            access_token_jti=jti,
            user_agent=user_agent,
            ip_address=ip_address,
        )
        await revoke_refresh_token(refresh_token, reason="rotated")
        return AuthTokens(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
        )

    async def change_password(
        self,
        user_id: str,
        current_password: str,
        new_password: str,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        user = await self.adapter.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id)

        if not verify_password(current_password, user.hashed_password):
            raise CurrentPasswordInvalidError()

        now = now_utc_naive()
        await self.adapter.update_user_password(
            user_id=user_id,
            hashed_password=get_password_hash(new_password),
            now=now,
        )
        await self.adapter.commit()

        await revoke_all_user_tokens(user_id, reason="password_change")

        await self.adapter.create_password_change_event(
            user_id=user_id,
            changed_at=now,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self.adapter.commit()

    async def forgot_password(self, email: str) -> str | None:
        user = await self.adapter.get_user_by_email(email.lower())
        if user is None:
            return None

        token = secrets.token_urlsafe(32)
        now = now_utc_naive()
        expires_at = now + timedelta(hours=1)

        await self.adapter.mark_unused_password_reset_tokens_used(user.id)
        await self.adapter.create_password_reset_token(
            token_id=str(uuid4()),
            user_id=user.id,
            token=token,
            expires_at=expires_at,
            created_at=now,
        )
        await self.adapter.commit()
        return token

    async def reset_password(self, token: str, new_password: str) -> None:
        reset_token = await self.adapter.get_password_reset_token(token)
        if reset_token is None:
            raise InvalidResetTokenError()
        if reset_token.expires_at < now_utc_naive():
            raise ExpiredResetTokenError()

        user = await self.adapter.get_user_by_id(reset_token.user_id)
        if user is None:
            raise UserNotFoundError(user_id=reset_token.user_id)

        await self.adapter.update_user_password(
            user_id=user.id,
            hashed_password=get_password_hash(new_password),
            now=now_utc_naive(),
        )
        await self.adapter.mark_password_reset_token_used(reset_token.id)
        await self.adapter.commit()

        await revoke_all_user_tokens(user.id)

    async def update_avatar(self, user_id: str, avatar_url: str | None) -> AuthUserRecord:
        updated = await self.adapter.update_user_avatar(
            user_id=user_id,
            avatar_url=avatar_url,
            now=now_utc_naive(),
        )
        if updated is None:
            raise UserNotFoundError(user_id=user_id)
        await self.adapter.commit()
        return updated
