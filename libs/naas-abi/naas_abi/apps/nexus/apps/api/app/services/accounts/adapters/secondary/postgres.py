"""Nexus's rows of the accounts: ``users``, ``auth_sessions``, the organization
profiles (``organization_members``) and the workspace rows of the old memberships."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    AccountStorePort,
    NexusUser,
    OrganizationRole,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

# A deleted account's email: ``.internal`` is reserved and never delegated, so no
# lookup, invitation or sign-in finds the row again (as ``@unverified.internal``).
RETIRED_EMAIL_DOMAIN = "deleted.internal"


def retired_email(user_id: str) -> str:
    return f"{user_id}@{RETIRED_EMAIL_DOMAIN}"


def _user(row: UserModel) -> NexusUser:
    return NexusUser(
        id=row.id,
        email=row.email,
        name=row.name,
        created_at=row.created_at,
        avatar=row.avatar,
        principal_id=row.principal_id,
        idp_provider=row.idp_provider,
        idp_subject=row.idp_subject,
    )


class AccountStorePostgres(AccountStorePort):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list_users(self) -> list[NexusUser]:
        rows = await self.db.execute(
            select(UserModel).where(UserModel.deleted_at.is_(None)).order_by(UserModel.email)
        )
        return [_user(row) for row in rows.scalars()]

    async def get_user(self, user_id: str) -> NexusUser | None:
        row = (
            await self.db.execute(
                select(UserModel).where(UserModel.id == user_id, UserModel.deleted_at.is_(None))
            )
        ).scalar_one_or_none()
        return _user(row) if row is not None else None

    async def user_by_email(self, email: str) -> NexusUser | None:
        row = (
            await self.db.execute(
                select(UserModel).where(
                    func.lower(UserModel.email) == email.lower().strip(),
                    UserModel.deleted_at.is_(None),
                )
            )
        ).scalar_one_or_none()
        return _user(row) if row is not None else None

    async def rename(self, user_id: str, name: str, *, now: datetime) -> None:
        await self.db.execute(
            update(UserModel).where(UserModel.id == user_id).values(name=name, updated_at=now)
        )

    async def set_superadmin_flag(self, user_id: str, on: bool, *, now: datetime) -> None:
        await self.db.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(is_superadmin=on, updated_at=now)
        )

    async def count_sessions(self, user_id: str, *, now: datetime) -> int:
        result = await self.db.execute(
            select(func.count())
            .select_from(AuthSessionModel)
            .where(
                AuthSessionModel.user_id == user_id,
                AuthSessionModel.revoked_at.is_(None),
                AuthSessionModel.expires_at > now,
            )
        )
        return int(result.scalar_one())

    async def end_sessions(self, user_id: str, *, now: datetime) -> int:
        result = await self.db.execute(
            update(AuthSessionModel)
            .where(AuthSessionModel.user_id == user_id, AuthSessionModel.revoked_at.is_(None))
            .values(revoked_at=now)
            .execution_options(synchronize_session=False)
        )
        return int(result.rowcount or 0)  # type: ignore[attr-defined]

    async def retire(self, user_id: str, *, now: datetime) -> None:
        await self.db.execute(delete(AuthSessionModel).where(AuthSessionModel.user_id == user_id))
        await self.db.execute(
            delete(OrganizationMemberModel).where(OrganizationMemberModel.user_id == user_id)
        )
        await self.db.execute(
            delete(WorkspaceMemberModel).where(WorkspaceMemberModel.user_id == user_id)
        )
        await self.db.execute(
            update(UserModel)
            .where(UserModel.id == user_id)
            .values(
                email=retired_email(user_id),
                avatar=None,
                is_superadmin=False,
                deleted_at=now,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )

    async def organizations(self) -> dict[str, list[OrganizationRole]]:
        service = OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=self.db))
        found: dict[str, list[OrganizationRole]] = {}
        for membership in await service.list_all_memberships():
            found.setdefault(membership.user_id, []).append(
                OrganizationRole(
                    membership.organization_id, membership.organization_name, membership.role
                )
            )
        return found

    async def workspace_names(self, ids: Sequence[str]) -> dict[str, str]:
        if not ids:
            return {}
        rows = await self.db.execute(
            select(WorkspaceModel.id, WorkspaceModel.name).where(WorkspaceModel.id.in_(list(ids)))
        )
        return {str(i): str(n) for i, n in rows.all()}

    async def organization_names(self, ids: Sequence[str]) -> dict[str, str]:
        if not ids:
            return {}
        rows = await self.db.execute(
            select(OrganizationModel.id, OrganizationModel.name).where(
                OrganizationModel.id.in_(list(ids))
            )
        )
        return {str(i): str(n) for i, n in rows.all()}

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()
