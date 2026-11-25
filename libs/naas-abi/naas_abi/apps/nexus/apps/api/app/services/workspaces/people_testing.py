"""An in-memory people service for the member routes' and the tools' tests.

It keeps its users in memory and gives access through the real people service and
its IAM gateway (``EngineAccessGateway`` over ``MEMBERSHIPS``), on behalf of ``by``,
so IAM still decides who may give what: only the account store, the provider and
the mail are faked. It raises ``services/people``'s own errors. Installed for every
caller (routes, agent tools, platform invite) the way the real service is, through
the people runtime: ``with installed(fake): ...``.
"""

from __future__ import annotations

from collections.abc import Collection, Iterable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any

from naas_abi.apps.nexus.apps.api.app.services.iam import runtime as iam_runtime
from naas_abi.apps.nexus.apps.api.app.services.people import runtime as people_runtime
from naas_abi.apps.nexus.apps.api.app.services.people.adapters.secondary.engine import (
    EngineAccessGateway,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    AddedUser,
    CreateOrLinkResult,
    Grant,
    IdentityGateway,
    Level,
    NewUser,
    PeopleMailer,
    PeopleStorePort,
    PlatformUser,
    ProviderInfo,
    Provisioned,
    UnknownUserError,
    UserStatus,
    WorkspaceAccess,
)
from naas_abi.apps.nexus.apps.api.app.services.people.service import PeopleService

NEXUS = ProviderInfo("nexus", "Nexus", "https://nexus.test", "builtin")


@contextmanager
def installed(people: Any) -> Iterator[Any]:
    """``people`` is the people service of every caller until the block ends."""
    previous = people_runtime.configure(people)
    try:
        yield people
    finally:
        people_runtime.configure(previous)


class _Rows(PeopleStorePort):
    """The fake's users, as the real service reads them (it only reads here)."""

    def __init__(self, fake: FakePeopleService) -> None:
        self.fake = fake

    async def get(self, user_id):
        return self.fake.users.get(user_id)

    async def by_email(self, email):
        return await self.fake.by_email(email)

    async def search(self, q, among, limit):
        return []

    async def add(self, user: NewUser, *, now):
        raise NotImplementedError("The fake makes its own rows")

    async def remove(self, user_id):
        self.fake.users.pop(user_id, None)

    async def activate(self, user_id, *, now):
        return False

    async def write_profile(self, organization_id, user_id, profile):
        return None

    async def record_provisioned(self, provider, subject, email, *, now):
        return None

    async def forget_provisioned(self, provider, subject):
        return None

    async def provider_for_domain(self, domain, organization_id):
        return None

    async def names(self, organization_id, workspace_id):
        return None, None

    async def commit(self):
        return None

    async def rollback(self):
        return None


class _NoIdp(IdentityGateway):
    async def providers(self):
        return [NEXUS], NEXUS.name

    async def provision(self, provider, email, name, *, by=None) -> Provisioned | None:
        return None

    async def delete(self, provider, subject):
        return None


class _Silent(PeopleMailer):
    async def invitation(self, **_kwargs):
        return True

    async def added(self, **_kwargs):
        return True


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

    def _real(self) -> PeopleService:
        return PeopleService(
            _Rows(self),
            _NoIdp(),
            EngineAccessGateway(iam_runtime.iam),
            _Silent(),
            clock=lambda: datetime.now(UTC),
        )

    async def create_or_link(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        grant: Grant | None,
        by: Any,
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
                    "grant": grant,
                    "by": getattr(by, "id", by),
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
            self.users[user.id] = user
        if grant is not None:
            try:
                await self._real().add_existing(user_id=user.id, grant=grant, by=by)
            except Exception:
                if created:
                    self.users.pop(user.id, None)
                raise
        return CreateOrLinkResult(
            user=user,
            created=created,
            provisioned=created,
            sign_in_email_sent=self.sent,
            warning=None,
            provider=NEXUS,
        )

    async def add_existing(
        self, *, user_id: str, grant: Grant, by: Any, notify: bool = True
    ) -> AddedUser:
        self.calls.append(
            (
                "add_existing",
                {"user_id": user_id, "grant": grant, "by": getattr(by, "id", by), "notify": notify},
            )
        )
        user = self.users.get(user_id)
        if user is None:
            raise UnknownUserError(user_id)
        await self._real().add_existing(user_id=user_id, grant=grant, by=by, notify=notify)
        return AddedUser(**user.__dict__, sign_in_email_sent=self.sent and notify)

    async def set_level(
        self, *, user_id: str, level: str, by: Any, where: Sequence[str] = ()
    ) -> Level | None:
        self.calls.append(
            ("set_level", {"user_id": user_id, "level": level, "by": getattr(by, "id", by)})
        )
        return await self._real().set_level(user_id=user_id, level=level, by=by, where=where)

    async def set_workspace_admin(
        self, *, user_id: str, workspace_id: str, admin: bool, by: Any
    ) -> None:
        self.calls.append(
            (
                "set_workspace_admin",
                {"user_id": user_id, "admin": admin, "by": getattr(by, "id", by)},
            )
        )
        await self._real().set_workspace_admin(
            user_id=user_id, workspace_id=workspace_id, admin=admin, by=by
        )

    async def change_access(
        self,
        *,
        user_id: str,
        organization_id: str,
        by: Any,
        level: str | None = None,
        org_admin: bool | None = None,
        workspaces: Sequence[WorkspaceAccess] | None = None,
        among: Sequence[str] = (),
        capabilities: Sequence[str] | None = None,
    ) -> None:
        self.calls.append(("change_access", {"user_id": user_id, "by": getattr(by, "id", by)}))
        await self._real().change_access(
            user_id=user_id,
            organization_id=organization_id,
            by=by,
            level=level,
            org_admin=org_admin,
            workspaces=workspaces,
            among=among,
            capabilities=capabilities,
        )

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
