from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import UserModel
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthPersistencePort,
    AuthUserRecord,
)
from sqlalchemy import select
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
            company=model.company,
            role=model.role,
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
        company: str | None,
        role: str | None,
        bio: str | None,
    ) -> AuthUserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return None

        if name is not None:
            user.name = name
        if company is not None:
            user.company = company
        if role is not None:
            user.role = role
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

    async def commit(self) -> None:
        await self.db.commit()
