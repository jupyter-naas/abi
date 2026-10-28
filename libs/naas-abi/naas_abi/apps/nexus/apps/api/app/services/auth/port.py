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
    organization: str | None = None
    job_title: str | None = None
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
        organization: str | None,
        job_title: str | None,
        bio: str | None,
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def update_user_avatar(
        self, user_id: str, avatar_url: str, now: datetime
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_users(self) -> list[AuthUserRecord]:
        raise NotImplementedError

    @abstractmethod
    async def count_superadmins(self) -> int:
        raise NotImplementedError

    @abstractmethod
    async def list_member_profiles(self, user_id: str) -> list[dict[str, str | None]]:
        """The user's organization member profiles (avatar, organization, job_title),
        oldest membership first: the account falls back to them (account_fallbacks)."""
        raise NotImplementedError

    @abstractmethod
    async def get_workspace_member_profile(
        self, user_id: str, workspace_id: str
    ) -> dict[str, str | None] | None:
        """The user's member profile (organization, job_title, bio) in the
        organization owning ``workspace_id``; None outside an organization."""
        raise NotImplementedError

    @abstractmethod
    async def set_user_superadmin(
        self, user_id: str, is_superadmin: bool, now: datetime
    ) -> AuthUserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def commit(self) -> None:
        raise NotImplementedError
