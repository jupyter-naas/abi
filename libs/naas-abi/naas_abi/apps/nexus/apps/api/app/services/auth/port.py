from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class AuthUserRecord:
    id: str
    email: str
    name: str
    created_at: datetime
    avatar: str | None = None
    company: str | None = None
    role: str | None = None
    bio: str | None = None
    is_superadmin: bool = False


class AuthPersistencePort(ABC):
    """Nexus's user rows, for the account's own routes. Nexus signs nobody in:
    people are created by their identity provider's first sign-in
    (``services/oidc``) and by invitations."""

    @abstractmethod
    async def get_user_by_id(self, user_id: str) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_email(self, email: str) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def update_user_profile(
        self,
        user_id: str,
        name: str | None,
        company: str | None,
        role: str | None,
        bio: str | None,
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def update_user_avatar(
        self, user_id: str, avatar_url: str, now: datetime
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError
