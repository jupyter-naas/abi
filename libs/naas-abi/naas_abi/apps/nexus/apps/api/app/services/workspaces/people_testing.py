"""An in-memory people service for the member routes' and the tools' tests.

It keeps its users in memory and grants through the real ``MEMBERSHIPS``, on
behalf of ``by``, so IAM still decides who may grant what: only the account
store, the provider and the mail are faked. It raises ``services/people``'s own
errors. Installed for every caller (routes, agent tools, platform invite) the way
the real service is, through the people runtime: ``with installed(fake): ...``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MEMBERSHIPS
from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container
from naas_abi.apps.nexus.apps.api.app.services.people import runtime as people_runtime
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AddedUser,
    AlreadyMemberError,
    CreateOrLinkResult,
    Grant,
    OwnerGrantRefusedError,
    PlatformUser,
    ProviderInfo,
    UnknownUserError,
    UserStatus,
)

NEXUS = ProviderInfo("nexus", "Nexus", "https://nexus.test", "builtin")


@contextmanager
def installed(people: Any) -> Iterator[Any]:
    """``people`` is the people service of every caller until the block ends."""
    previous = people_runtime.configure(people)
    try:
        yield people
    finally:
        people_runtime.configure(previous)


@dataclass
class FakePeopleService:
    users: dict[str, PlatformUser] = field(default_factory=dict)
    calls: list[tuple[str, dict[str, Any]]] = field(default_factory=list)
    sent: bool = True

    @classmethod
    def of(cls, *users: tuple[str, str, str | None]) -> FakePeopleService:
        """Active users from ``(id, email, name)``."""
        return cls(
            users={
                user_id: PlatformUser(user_id, email, name, UserStatus.ACTIVE, "nexus")
                for user_id, email, name in users
            }
        )

    def service(self, _db: Any) -> FakePeopleService:
        """The people runtime's factory (``installed``): this service, any session."""
        return self

    def invited(self, user_id: str) -> None:
        self.users[user_id] = replace(self.users[user_id], status=UserStatus.INVITED)

    async def _scope(self, grant: Grant) -> str:
        if grant.scope == "organization":
            return org_container(grant.scope_id)
        scope = await AUTHZ.container_of(grant.scope_id)
        if scope is None:
            raise ValueError(f"Unknown workspace {grant.scope_id}")
        return scope

    async def _attach(
        self, user_id: str, grants: Sequence[Grant], by: Any, may_grant_owner: bool
    ) -> None:
        if any(g.role == "owner" for g in grants) and not may_grant_owner:
            raise OwnerGrantRefusedError("Only an owner can make an owner")
        scopes = [(await self._scope(g), g) for g in grants]
        held = [await MEMBERSHIPS.role_at(user_id, s) for s, g in scopes if g.role is not None]
        if held and all(r is not None for r in held):
            raise AlreadyMemberError(user_id, scopes[0][0])
        for scope, grant in scopes:
            if grant.role is not None:
                await MEMBERSHIPS.grant(user_id, grant.role, scope, by=by)

    async def create_or_link(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        grants: Sequence[Grant],
        by: Any,
        may_grant_owner: bool = False,
        profile: Mapping[str, str] | None = None,
        organization_id: str | None = None,
    ) -> CreateOrLinkResult:
        self.calls.append(
            (
                "create_or_link",
                {
                    "email": email,
                    "name": name,
                    "provider": provider,
                    "grants": tuple(grants),
                    "by": getattr(by, "id", by),
                    "may_grant_owner": may_grant_owner,
                    "profile": dict(profile or {}),
                    "organization_id": organization_id,
                },
            )
        )
        user = await self.by_email(email)
        created = user is None
        if user is None:
            user = PlatformUser(
                f"new-{len(self.users) + 1}", email, name, UserStatus.INVITED, provider
            )
        await self._attach(user.id, grants, by, may_grant_owner)
        self.users[user.id] = user
        return CreateOrLinkResult(
            user=user,
            created=created,
            provisioned=created,
            sign_in_email_sent=self.sent,
            warning=None,
            provider=NEXUS,
        )

    async def add_existing(
        self, *, user_id: str, grants: Sequence[Grant], by: Any, may_grant_owner: bool = False
    ) -> AddedUser:
        self.calls.append(
            (
                "add_existing",
                {
                    "user_id": user_id,
                    "grants": tuple(grants),
                    "by": getattr(by, "id", by),
                    "may_grant_owner": may_grant_owner,
                },
            )
        )
        user = self.users.get(user_id)
        if user is None:
            raise UnknownUserError(user_id)
        await self._attach(user_id, grants, by, may_grant_owner)
        return AddedUser(**user.__dict__, sign_in_email_sent=self.sent)

    async def get(self, user_id: str) -> PlatformUser | None:
        return self.users.get(user_id)

    async def by_email(self, email: str) -> PlatformUser | None:
        wanted = email.strip().lower()
        return next((u for u in self.users.values() if u.email.lower() == wanted), None)

    async def search(
        self, *, q: str, among: Collection[str], limit: int = 10
    ) -> list[PlatformUser]:
        self.calls.append(("search", {"q": q, "among": set(among), "limit": limit}))
        needle = q.strip().lower()
        found = [
            u
            for u in self.users.values()
            if u.id in among and (needle in u.email.lower() or needle in (u.name or "").lower())
        ]
        return sorted(found, key=lambda u: u.email)[:limit]

    async def resend(self, *, user_id: str, by: Any) -> bool:
        self.calls.append(("resend", {"user_id": user_id, "by": getattr(by, "id", by)}))
        return self.sent

    async def activate(self, user_id: str) -> None:
        self.users[user_id] = replace(self.users[user_id], status=UserStatus.ACTIVE)

    def named(self, kind: str) -> list[dict[str, Any]]:
        return [args for name, args in self.calls if name == kind]


def team_people(users: Iterable[str]) -> FakePeopleService:
    """The test team's users (``owner``, ``admin``…), as ``<id>@example.com``."""
    return FakePeopleService.of(*((u, f"{u}@example.com", u.title()) for u in users))
