"""The signed-in user's account: profile and avatar.

Nexus signs nobody in: a person's identity provider does (``services/oidc``), and
a session is the cookie that sign-in sets, or an API key (``credentials.py``). No
password, no one-time code, no token signed here: the code of those logins, and the
tables they used, were removed (RFC §13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthPersistencePort,
    AuthUserRecord,
)


@dataclass
class UserNotFoundError(ValueError):
    user_id: str | None = None

    def __str__(self) -> str:
        return "user_not_found"


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthService:
    def __init__(self, adapter: AuthPersistencePort):
        self.adapter = adapter

    async def update_profile(
        self,
        user_id: str,
        name: str | None,
        company: str | None,
        role: str | None,
        bio: str | None,
    ) -> AuthUserRecord:
        """Edit what the person says about themselves. The email is never edited
        here: it is how invitations find an account, and the identity provider
        states it (a profile edit proves nothing about an address)."""
        updated_user = await self.adapter.update_user_profile(
            user_id=user_id,
            name=name,
            company=company,
            role=role,
            bio=bio,
        )
        if updated_user is None:
            raise UserNotFoundError(user_id=user_id)
        await self.adapter.commit()
        return updated_user

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
