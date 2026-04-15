from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuthUserRecord:
    id: str
    email: str
    name: str
    hashed_password: str
    created_at: datetime
    avatar: str | None = None
    company: str | None = None
    role: str | None = None
    bio: str | None = None


@dataclass
class PasswordResetTokenRecord:
    id: str
    user_id: str
    token: str
    expires_at: datetime
    used: bool
    created_at: datetime


@dataclass
class MagicLinkTokenRecord:
    id: str
    user_id: str
    token: str
    expires_at: datetime
    used: bool
    created_at: datetime


class AuthPersistencePort(ABC):
    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_email(self, email: str) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def user_exists_with_email(self, email: str, exclude_user_id: str | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_user_with_personal_workspace(
        self,
        user_id: str,
        email: str,
        name: str,
        hashed_password: str,
        now: datetime,
    ) -> AuthUserRecord:
        raise NotImplementedError

    @abstractmethod
    async def update_user_profile(
        self,
        user_id: str,
        name: str | None,
        email: str | None,
        company: str | None,
        role: str | None,
        bio: str | None,
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def update_user_password(self, user_id: str, hashed_password: str, now: datetime) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_password_change_event(
        self,
        user_id: str,
        changed_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_unused_password_reset_tokens_used(self, user_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_password_reset_token(
        self,
        token_id: str,
        user_id: str,
        token: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_password_reset_token(self, token: str) -> PasswordResetTokenRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def mark_password_reset_token_used(self, token_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def mark_unused_magic_link_tokens_used(self, user_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def create_magic_link_token(
        self,
        token_id: str,
        user_id: str,
        token: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        raise NotImplementedError

    @abstractmethod
    async def get_magic_link_token(self, token: str) -> MagicLinkTokenRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def mark_magic_link_token_used(self, token_id: str) -> None:
        raise NotImplementedError

    @abstractmethod
    async def update_user_avatar(
        self, user_id: str, avatar_url: str, now: datetime
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError
