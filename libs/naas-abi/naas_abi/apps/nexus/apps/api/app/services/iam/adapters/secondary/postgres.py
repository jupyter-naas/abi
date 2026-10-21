from __future__ import annotations

from collections.abc import Callable
from typing import cast

from naas_abi.apps.nexus.apps.api.app.core.workspace_access import (
    resolve_organization_role,
    resolve_workspace_role,
)
from naas_abi.apps.nexus.apps.api.app.models import ConversationModel
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
        return cast(Role | None, await resolve_workspace_role(self.db, user_id, workspace_id))

    async def get_organization_role(self, user_id: str, org_id: str) -> Role | None:
        return cast(Role | None, await resolve_organization_role(self.db, user_id, org_id))

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
