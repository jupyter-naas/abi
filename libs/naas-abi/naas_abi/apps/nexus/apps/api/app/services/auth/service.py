"""The signed-in user's account: profile and avatar.

Nexus signs nobody in: a person's identity provider does (``services/oidc``), and
a session is the cookie that sign-in sets, or an API key (``credentials.py``). No
password, no one-time code, no token signed here: the code of those logins, and the
tables they used, were removed.

Who is a platform administrator is IAM's (``builtin.platform_admin``): the stored
``is_superadmin`` flag is only what the account list shows, read from IAM.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.services.auth.account_fallbacks import (
    FALLBACK_FIELDS,
    effective_account_values,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthPersistencePort,
    AuthUserRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS, Memberships


@dataclass
class UserNotFoundError(ValueError):
    user_id: str | None = None

    def __str__(self) -> str:
        return "user_not_found"


@dataclass
class SuperadminChangeError(ValueError):
    reason: str  # cannot_demote_self | last_superadmin

    def __str__(self) -> str:
        return self.reason


def now_utc_naive() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


class AuthService:
    def __init__(self, adapter: AuthPersistencePort, memberships: Memberships = MEMBERSHIPS):
        self.adapter = adapter
        self.memberships = memberships

    async def update_profile(
        self,
        user_id: str,
        name: str | None,
        organization: str | None,
        job_title: str | None,
        bio: str | None,
    ) -> AuthUserRecord:
        """Edit what the person says about themselves. The email is never edited
        here: it is how invitations find an account, and the identity provider
        states it (a profile edit proves nothing about an address)."""
        updated_user = await self.adapter.update_user_profile(
            user_id=user_id,
            name=name,
            organization=organization,
            job_title=job_title,
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

    async def list_users(self) -> list[AuthUserRecord]:
        """Every account, with ``is_superadmin`` as IAM holds it."""
        admins = await self.memberships.platform_admins()
        return [
            replace(user, is_superadmin=user.id in admins)
            for user in await self.adapter.list_users()
        ]

    async def get_user(self, user_id: str) -> AuthUserRecord | None:
        return await self.adapter.get_user_by_id(user_id)

    async def with_account_fallbacks(self, user: AuthUserRecord) -> AuthUserRecord:
        """The account as shown to its owner: empty picture, organization and job
        title filled from their organization member profiles (org -> account only)."""
        if all(getattr(user, field) for field in FALLBACK_FIELDS):
            return user
        profiles = await self.adapter.list_member_profiles(user.id)
        effective = effective_account_values(
            {field: getattr(user, field) for field in FALLBACK_FIELDS}, profiles
        )
        return replace(user, **effective)

    async def set_superadmin(
        self, *, actor_id: str, user_id: str, is_superadmin: bool
    ) -> AuthUserRecord:
        """Promote or demote a platform administrator: attach or detach IAM's
        ``builtin.platform_admin`` for the user, as the actor (IAM checks that they
        may). Never leaves the platform without one."""
        user = await self.adapter.get_user_by_id(user_id)
        if user is None:
            raise UserNotFoundError(user_id=user_id)
        admins = await self.memberships.platform_admins()
        if (user_id in admins) == is_superadmin:
            return replace(user, is_superadmin=is_superadmin)
        if not is_superadmin:
            if user_id == actor_id:
                raise SuperadminChangeError(reason="cannot_demote_self")
            if len(admins) <= 1:
                raise SuperadminChangeError(reason="last_superadmin")
        await self.memberships.set_platform_admin(user_id, is_superadmin, by=actor_id)
        # The stored flag only bootstraps (config promotes on boot): keep it in step.
        await self.adapter.set_user_superadmin(
            user_id=user_id, is_superadmin=is_superadmin, now=now_utc_naive()
        )
        await self.adapter.commit()
        return replace(user, is_superadmin=is_superadmin)
