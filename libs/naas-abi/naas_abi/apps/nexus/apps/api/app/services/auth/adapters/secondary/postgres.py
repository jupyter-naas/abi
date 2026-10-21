from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationMemberModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthPersistencePort,
    AuthUserRecord,
)
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class AuthSecondaryAdapterPostgres(AuthPersistencePort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("AuthSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    @staticmethod
    def _to_user_record(model: UserModel) -> AuthUserRecord:
        return AuthUserRecord(
            id=model.id,
            email=model.email,
            name=model.name,
            avatar=model.avatar,
            organization=model.organization,
            job_title=model.job_title,
            bio=model.bio,
            is_superadmin=bool(model.is_superadmin),
            created_at=model.created_at,
        )

    async def get_user_by_id(self, user_id: str) -> AuthUserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_user_record(row)

    async def get_user_by_email(self, email: str) -> AuthUserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.email == email))
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_user_record(row)

    async def update_user_profile(
        self,
        user_id: str,
        name: str | None,
        organization: str | None,
        job_title: str | None,
        bio: str | None,
    ) -> AuthUserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        if name is not None:
            user.name = name
        if organization is not None:
            user.organization = organization
        if job_title is not None:
            user.job_title = job_title
        if bio is not None:
            user.bio = bio

        await self.db.flush()
        await self.db.refresh(user)
        return self._to_user_record(user)

    async def update_user_avatar(
        self, user_id: str, avatar_url: str | None, now: datetime
    ) -> AuthUserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.avatar = avatar_url
        user.updated_at = now
        await self.db.flush()
        await self.db.refresh(user)
        return self._to_user_record(user)

    async def list_users(self) -> list[AuthUserRecord]:
        result = await self.db.execute(select(UserModel).order_by(UserModel.email))
        return [self._to_user_record(user) for user in result.scalars().all()]

    async def count_superadmins(self) -> int:
        result = await self.db.execute(
            select(func.count()).select_from(UserModel).where(UserModel.is_superadmin.is_(True))
        )
        return int(result.scalar_one())

    async def list_member_profiles(self, user_id: str) -> list[dict[str, str | None]]:
        rows = await self.db.execute(
            select(
                OrganizationMemberModel.avatar,
                OrganizationMemberModel.organization_name,
                OrganizationMemberModel.job_title,
            )
            .where(OrganizationMemberModel.user_id == user_id)
            .order_by(OrganizationMemberModel.created_at, OrganizationMemberModel.id)
        )
        return [
            {"avatar": avatar, "organization": organization, "job_title": job_title}
            for avatar, organization, job_title in rows.all()
        ]

    async def get_workspace_member_profile(
        self, user_id: str, workspace_id: str
    ) -> dict[str, str | None] | None:
        row = (
            await self.db.execute(
                select(
                    OrganizationMemberModel.organization_name,
                    OrganizationMemberModel.job_title,
                    OrganizationMemberModel.bio,
                )
                .join(
                    WorkspaceModel,
                    WorkspaceModel.organization_id == OrganizationMemberModel.organization_id,
                )
                .where(WorkspaceModel.id == workspace_id)
                .where(OrganizationMemberModel.user_id == user_id)
            )
        ).one_or_none()
        if row is None:
            return None
        organization, job_title, bio = row
        return {"organization": organization, "job_title": job_title, "bio": bio}

    async def set_user_superadmin(
        self, user_id: str, is_superadmin: bool, now: datetime
    ) -> AuthUserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        user.is_superadmin = is_superadmin
        user.updated_at = now
        await self.db.flush()
        await self.db.refresh(user)
        return self._to_user_record(user)

    async def commit(self) -> None:
        await self.db.commit()
