from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import (
    MagicLinkTokenModel,
    PasswordResetTokenModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.port import (
    AuthPersistencePort,
    AuthUserRecord,
    MagicLinkTokenRecord,
    PasswordResetTokenRecord,
)
from naas_abi.apps.nexus.apps.api.app.services.refresh_token import hash_token
from sqlalchemy import select, text
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
            hashed_password=model.hashed_password,
            avatar=model.avatar,
            company=model.company,
            role=model.role,
            bio=model.bio,
            created_at=model.created_at,
        )

    @staticmethod
    def _to_reset_token_record(model: PasswordResetTokenModel) -> PasswordResetTokenRecord:
        return PasswordResetTokenRecord(
            id=model.id,
            user_id=model.user_id,
            token=model.token,
            expires_at=model.expires_at,
            used=bool(model.used),
            created_at=model.created_at,
        )

    @staticmethod
    def _to_magic_link_token_record(model: MagicLinkTokenModel) -> MagicLinkTokenRecord:
        return MagicLinkTokenRecord(
            id=model.id,
            user_id=model.user_id,
            token=model.token,
            expires_at=model.expires_at,
            used=bool(model.used),
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

    async def user_exists_with_email(self, email: str, exclude_user_id: str | None = None) -> bool:
        stmt = select(UserModel.id).where(UserModel.email == email)
        if exclude_user_id is not None:
            stmt = stmt.where(UserModel.id != exclude_user_id)
        result = await self.db.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def create_user_with_personal_workspace(
        self,
        user_id: str,
        email: str,
        name: str,
        hashed_password: str,
        now: datetime,
    ) -> AuthUserRecord:
        user_row = UserModel(
            id=user_id,
            email=email,
            name=name,
            hashed_password=hashed_password,
            created_at=now,
            updated_at=now,
        )
        self.db.add(user_row)

        personal_workspace = WorkspaceModel(
            id=user_id,
            name=f"{name}'s Personal Workspace",
            slug=f"personal-{user_id}",
            owner_id=user_id,
            created_at=now,
            updated_at=now,
        )
        self.db.add(personal_workspace)

        workspace_member = WorkspaceMemberModel(
            id=f"member-{uuid4().hex[:12]}",
            workspace_id=user_id,
            user_id=user_id,
            role="owner",
            created_at=now,
        )
        self.db.add(workspace_member)

        return self._to_user_record(user_row)

    async def update_user_profile(
        self,
        user_id: str,
        name: str | None,
        email: str | None,
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
        if email is not None:
            user.email = email
        if company is not None:
            user.company = company
        if role is not None:
            user.role = role
        if bio is not None:
            user.bio = bio

        await self.db.flush()
        await self.db.refresh(user)
        return self._to_user_record(user)

    async def update_user_password(self, user_id: str, hashed_password: str, now: datetime) -> bool:
        result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.hashed_password = hashed_password
        user.updated_at = now
        return True

    async def create_password_change_event(
        self,
        user_id: str,
        changed_at: datetime,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        pw_change_id = f"pwc-{uuid4().hex[:12]}"
        await self.db.execute(
            text(
                """
                INSERT INTO password_changes (id, user_id, changed_at, ip_address, user_agent)
                VALUES (:id, :user_id, :changed_at, :ip_address, :user_agent)
                """
            ),
            {
                "id": pw_change_id,
                "user_id": user_id,
                "changed_at": changed_at,
                "ip_address": ip_address,
                "user_agent": user_agent,
            },
        )

    async def mark_unused_password_reset_tokens_used(self, user_id: str) -> None:
        result = await self.db.execute(
            select(PasswordResetTokenModel).where(
                (PasswordResetTokenModel.user_id == user_id)
                & (PasswordResetTokenModel.used.is_(False))
            )
        )
        for row in result.scalars().all():
            row.used = True

    async def create_password_reset_token(
        self,
        token_id: str,
        user_id: str,
        token: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        self.db.add(
            PasswordResetTokenModel(
                id=token_id,
                user_id=user_id,
                token=token,
                expires_at=expires_at,
                used=False,
                created_at=created_at,
            )
        )

    async def get_password_reset_token(self, token: str) -> PasswordResetTokenRecord | None:
        token_hash = hash_token(token)
        result = await self.db.execute(
            select(PasswordResetTokenModel).where(
                (
                    (PasswordResetTokenModel.token == token_hash)
                    | (PasswordResetTokenModel.token == token)
                )
                & (PasswordResetTokenModel.used.is_(False))
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_reset_token_record(row)

    async def mark_password_reset_token_used(self, token_id: str) -> None:
        result = await self.db.execute(
            select(PasswordResetTokenModel).where(PasswordResetTokenModel.id == token_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.used = True

    async def mark_unused_magic_link_tokens_used(
        self,
        user_id: str,
        keep_latest_unused: int = 0,
    ) -> None:
        if keep_latest_unused < 0:
            keep_latest_unused = 0

        statement = (
            select(MagicLinkTokenModel)
            .where((MagicLinkTokenModel.user_id == user_id) & (MagicLinkTokenModel.used.is_(False)))
            .order_by(MagicLinkTokenModel.created_at.desc())
            .offset(keep_latest_unused)
        )
        result = await self.db.execute(statement)
        for row in result.scalars().all():
            row.used = True

    async def create_magic_link_token(
        self,
        token_id: str,
        user_id: str,
        token: str,
        expires_at: datetime,
        created_at: datetime,
    ) -> None:
        self.db.add(
            MagicLinkTokenModel(
                id=token_id,
                user_id=user_id,
                token=token,
                expires_at=expires_at,
                used=False,
                created_at=created_at,
            )
        )

    async def get_magic_link_token(self, token: str) -> MagicLinkTokenRecord | None:
        token_hash = hash_token(token)
        result = await self.db.execute(
            select(MagicLinkTokenModel).where(
                ((MagicLinkTokenModel.token == token_hash) | (MagicLinkTokenModel.token == token))
                & (MagicLinkTokenModel.used.is_(False))
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_magic_link_token_record(row)

    async def mark_magic_link_token_used(self, token_id: str) -> None:
        result = await self.db.execute(
            select(MagicLinkTokenModel).where(MagicLinkTokenModel.id == token_id)
        )
        row = result.scalar_one_or_none()
        if row is not None:
            row.used = True

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
