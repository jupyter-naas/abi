"""``PeopleStorePort`` on Nexus's database (PostgreSQL or SQLite)."""

from __future__ import annotations

from collections.abc import Collection, Mapping
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationDomainModel,
    OrganizationModel,
    ProvisionedIdentityModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    EmailTakenError,
    NewUser,
    PeopleStorePort,
    PlatformUser,
    UserStatus,
)
from sqlalchemy import delete, func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession


def _user(row: UserModel) -> PlatformUser:
    status = str(row.status or "")
    return PlatformUser(
        id=str(row.id),
        email=str(row.email),
        name=str(row.name) if row.name is not None else None,
        # A value no release writes reads as the default (``active``).
        status=UserStatus(status) if status in UserStatus._value2member_map_ else UserStatus.ACTIVE,
        provider=str(row.idp_provider) if row.idp_provider is not None else None,
    )


class PeopleSecondaryAdapterPostgres(PeopleStorePort):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, user_id: str) -> PlatformUser | None:
        row = (
            await self.db.execute(
                select(UserModel).where(UserModel.id == user_id, UserModel.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        return _user(row) if row is not None else None

    async def by_email(self, email: str) -> PlatformUser | None:
        row = (
            await self.db.execute(
                select(UserModel).where(
                    func.lower(UserModel.email) == email.strip().lower(),
                    UserModel.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        return _user(row) if row is not None else None

    async def search(self, q: str, among: Collection[str], limit: int) -> list[PlatformUser]:
        ids = list(dict.fromkeys(among))
        if not ids:
            return []
        needle = q.lower()
        rows = await self.db.execute(
            select(UserModel)
            .where(
                UserModel.id.in_(ids),
                UserModel.deleted_at.is_(None),
                or_(
                    func.lower(UserModel.name).contains(needle, autoescape=True),
                    func.lower(UserModel.email).contains(needle, autoescape=True),
                ),
            )
            .order_by(func.lower(UserModel.name), func.lower(UserModel.email))
            .limit(limit)
        )
        return [_user(row) for row in rows.scalars()]

    async def add(self, user: NewUser, *, now: datetime) -> PlatformUser:
        taken = (
            await self.db.execute(
                select(UserModel.id).where(func.lower(UserModel.email) == user.email.lower())
            )
        ).first()
        if taken is not None:
            raise EmailTakenError(user.email)
        model = UserModel(
            id=user.id,
            email=user.email.lower(),
            name=user.name,
            principal_id=user.principal_id,
            idp_provider=user.provider,
            idp_issuer=user.issuer,
            idp_subject=user.subject,
            status=UserStatus.INVITED.value,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        try:
            await self.db.flush()
        except IntegrityError as exc:
            # Another row took the email (or this identity) meanwhile.
            await self.db.rollback()
            raise EmailTakenError(user.email) from exc
        return _user(model)

    async def remove(self, user_id: str) -> None:
        await self.db.execute(
            delete(UserModel).where(
                UserModel.id == user_id, UserModel.status == UserStatus.INVITED.value
            )
        )

    async def activate(self, user_id: str, *, now: datetime) -> bool:
        result = await self.db.execute(
            update(UserModel)
            .where(UserModel.id == user_id, UserModel.status == UserStatus.INVITED.value)
            .values(status=UserStatus.ACTIVE.value, activated_at=now, updated_at=now)
            .execution_options(synchronize_session=False)
        )
        return bool(result.rowcount)  # type: ignore[attr-defined]

    async def write_profile(
        self, organization_id: str, user_id: str, profile: Mapping[str, str]
    ) -> None:
        await OrganizationSecondaryAdapterPostgres(self.db).update_organization_member_profile(
            organization_id,
            user_id,
            name=None,
            organization=profile.get("organization"),
            job_title=profile.get("job_title"),
            bio=profile.get("bio"),
            service_line=profile.get("service_line"),
            country=profile.get("country"),
            interest=profile.get("interest"),
        )

    async def record_provisioned(
        self, provider: str, subject: str, email: str, *, now: datetime
    ) -> None:
        if await self.db.get(ProvisionedIdentityModel, (provider, subject)) is None:
            self.db.add(
                ProvisionedIdentityModel(
                    provider=provider, subject=subject, email=email.lower(), created_at=now
                )
            )
            await self.db.flush()

    async def forget_provisioned(self, provider: str, subject: str) -> None:
        await self.db.execute(
            delete(ProvisionedIdentityModel).where(
                ProvisionedIdentityModel.provider == provider,
                ProvisionedIdentityModel.subject == subject,
            )
        )
        await self.db.commit()

    async def provider_for_domain(self, domain: str, organization_id: str | None) -> str | None:
        """A domain the organization verified routes to its provider; another
        organization's domains route nothing here."""
        if organization_id is None:
            return None
        return (
            await self.db.execute(
                select(OrganizationDomainModel.provider)
                .where(
                    OrganizationDomainModel.organization_id == organization_id,
                    func.lower(OrganizationDomainModel.domain) == domain.lower(),
                    OrganizationDomainModel.is_verified.is_(True),
                    OrganizationDomainModel.provider.is_not(None),
                )
                .order_by(OrganizationDomainModel.verified_at, OrganizationDomainModel.id)
                .limit(1)
            )
        ).scalar_one_or_none()

    async def names(
        self, organization_id: str | None, workspace_id: str | None
    ) -> tuple[str | None, str | None]:
        org_name = (
            (
                await self.db.execute(
                    select(OrganizationModel.name).where(OrganizationModel.id == organization_id)
                )
            ).scalar_one_or_none()
            if organization_id
            else None
        )
        ws_name = (
            (
                await self.db.execute(
                    select(WorkspaceModel.name).where(WorkspaceModel.id == workspace_id)
                )
            ).scalar_one_or_none()
            if workspace_id
            else None
        )
        return org_name, ws_name

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()
