from __future__ import annotations

from collections.abc import Callable

from naas_abi.apps.nexus.apps.api.app.models import (
    ConversationModel,
    OrganizationMemberModel,
    OrganizationModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.port import (
    ConversationAccessRecord,
    IAMPolicyPort,
    Role,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class IAMSecondaryAdapterPostgres(IAMPolicyPort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("IAMSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    async def get_workspace_role(self, user_id: str, workspace_id: str) -> Role | None:
        member_result = await self.db.execute(
            select(WorkspaceMemberModel.role)
            .where(WorkspaceMemberModel.workspace_id == workspace_id)
            .where(WorkspaceMemberModel.user_id == user_id)
        )
        member_role = member_result.scalar_one_or_none()
        if member_role is not None:
            return member_role

        owner_result = await self.db.execute(
            select(WorkspaceModel.owner_id).where(WorkspaceModel.id == workspace_id)
        )
        owner_id = owner_result.scalar_one_or_none()
        if owner_id == user_id:
            return "owner"
        return None

    async def get_organization_role(self, user_id: str, org_id: str) -> Role | None:
        member_result = await self.db.execute(
            select(OrganizationMemberModel.role)
            .where(OrganizationMemberModel.organization_id == org_id)
            .where(OrganizationMemberModel.user_id == user_id)
        )
        member_role = member_result.scalar_one_or_none()
        if member_role is not None:
            return member_role

        owner_result = await self.db.execute(
            select(OrganizationModel.owner_id).where(OrganizationModel.id == org_id)
        )
        owner_id = owner_result.scalar_one_or_none()
        if owner_id == user_id:
            return "owner"
        return None

    async def get_conversation_access_record(
        self, conversation_id: str
    ) -> ConversationAccessRecord | None:
        result = await self.db.execute(
            select(ConversationModel).where(ConversationModel.id == conversation_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return ConversationAccessRecord(
            conversation_id=row.id,
            workspace_id=row.workspace_id,
            owner_user_id=row.user_id,
        )
