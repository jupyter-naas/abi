from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import (
    AgentConfigModel,
    ConversationModel,
    GraphEdgeModel,
    GraphNodeModel,
    InferenceServerModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.port import (
    InferenceServerCreateInput,
    InferenceServerRecord,
    InferenceServerUpdateInput,
    UserRecord,
    WorkspaceCreateInput,
    WorkspaceMemberRecord,
    WorkspacePermissionPort,
    WorkspaceRecord,
    WorkspaceStatsRecord,
    WorkspaceUpdateInput,
)
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class WorkspaceSecondaryAdapterPostgres(WorkspacePermissionPort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("WorkspaceSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    async def get_workspace_role(self, user_id: str, workspace_id: str) -> str | None:
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

    @staticmethod
    def _to_workspace_record(model: WorkspaceModel) -> WorkspaceRecord:
        return WorkspaceRecord(
            id=model.id,
            name=model.name,
            slug=model.slug,
            owner_id=model.owner_id,
            organization_id=model.organization_id,
            logo_url=model.logo_url,
            logo_emoji=model.logo_emoji,
            primary_color=model.primary_color,
            accent_color=model.accent_color,
            background_color=model.background_color,
            sidebar_color=model.sidebar_color,
            font_family=model.font_family,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def _to_inference_server_record(model: InferenceServerModel) -> InferenceServerRecord:
        return InferenceServerRecord(
            id=model.id,
            workspace_id=model.workspace_id,
            name=model.name,
            type=model.type,
            endpoint=model.endpoint,
            description=model.description,
            enabled=model.enabled,
            api_key=model.api_key,
            health_path=model.health_path,
            models_path=model.models_path,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def _apply_org_logos(self, rows: list[WorkspaceRecord]) -> list[WorkspaceRecord]:
        org_ids = {row.organization_id for row in rows if row.organization_id}
        if not org_ids:
            return rows

        org_res = await self.db.execute(
            select(
                OrganizationModel.id,
                OrganizationModel.logo_url,
                OrganizationModel.logo_rectangle_url,
            ).where(OrganizationModel.id.in_(org_ids))
        )
        org_logo_map: dict[str, tuple[str | None, str | None]] = {}
        for org_id, logo_url, logo_rectangle_url in org_res.all():
            org_logo_map[org_id] = (logo_url, logo_rectangle_url)

        hydrated: list[WorkspaceRecord] = []
        for row in rows:
            if row.organization_id and row.organization_id in org_logo_map:
                logos = org_logo_map[row.organization_id]
                row.organization_logo_url = logos[0]
                row.organization_logo_rectangle_url = logos[1]
            hydrated.append(row)
        return hydrated

    async def list_workspaces_for_user(self, user_id: str) -> list[WorkspaceRecord]:
        result = await self.db.execute(
            select(WorkspaceModel)
            .outerjoin(WorkspaceMemberModel, WorkspaceModel.id == WorkspaceMemberModel.workspace_id)
            .where((WorkspaceModel.owner_id == user_id) | (WorkspaceMemberModel.user_id == user_id))
            .distinct()
            .order_by(WorkspaceModel.name)
        )
        rows = [self._to_workspace_record(row) for row in result.scalars().all()]
        return await self._apply_org_logos(rows)

    async def get_workspace_by_id(self, workspace_id: str) -> WorkspaceRecord | None:
        result = await self.db.execute(
            select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            return None
        rows = await self._apply_org_logos([self._to_workspace_record(workspace)])
        return rows[0]

    async def get_workspace_by_slug(self, slug: str) -> WorkspaceRecord | None:
        result = await self.db.execute(select(WorkspaceModel).where(WorkspaceModel.slug == slug))
        workspace = result.scalar_one_or_none()
        if workspace is None:
            return None
        rows = await self._apply_org_logos([self._to_workspace_record(workspace)])
        return rows[0]

    async def workspace_slug_exists(self, slug: str) -> bool:
        result = await self.db.execute(select(WorkspaceModel.id).where(WorkspaceModel.slug == slug))
        return result.scalar_one_or_none() is not None

    async def create_workspace(self, workspace: WorkspaceCreateInput) -> WorkspaceRecord:
        now = datetime.now(UTC).replace(tzinfo=None)
        workspace_id = f"ws-{uuid4().hex[:12]}"
        workspace_model = WorkspaceModel(
            id=workspace_id,
            name=workspace.name,
            slug=workspace.slug,
            owner_id=workspace.owner_id,
            organization_id=workspace.organization_id,
            logo_url=workspace.logo_url,
            logo_emoji=workspace.logo_emoji,
            primary_color=workspace.primary_color,
            accent_color=workspace.accent_color,
            background_color=workspace.background_color,
            sidebar_color=workspace.sidebar_color,
            font_family=workspace.font_family,
            created_at=now,
            updated_at=now,
        )
        self.db.add(workspace_model)
        self.db.add(
            WorkspaceMemberModel(
                id=str(uuid4()),
                workspace_id=workspace_id,
                user_id=workspace.owner_id,
                role="owner",
                created_at=now,
            )
        )
        await self.db.flush()
        return self._to_workspace_record(workspace_model)

    async def delete_workspace(self, workspace_id: str) -> bool:
        result = await self.db.execute(
            select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            return False
        await self.db.delete(workspace)
        return True

    async def update_workspace(
        self, workspace_id: str, updates: WorkspaceUpdateInput
    ) -> WorkspaceRecord | None:
        result = await self.db.execute(
            select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            return None

        update_data = {
            "name": updates.name,
            "logo_url": updates.logo_url,
            "logo_emoji": updates.logo_emoji,
            "primary_color": updates.primary_color,
            "accent_color": updates.accent_color,
            "background_color": updates.background_color,
            "sidebar_color": updates.sidebar_color,
            "font_family": updates.font_family,
        }
        for field, value in update_data.items():
            if value is not None:
                setattr(workspace, field, value)
        workspace.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.flush()
        return self._to_workspace_record(workspace)

    async def get_workspace_stats(self, workspace_id: str) -> WorkspaceStatsRecord | None:
        exists_result = await self.db.execute(
            select(WorkspaceModel.id).where(WorkspaceModel.id == workspace_id)
        )
        if exists_result.scalar_one_or_none() is None:
            return None

        nodes = (
            await self.db.execute(
                select(func.count())
                .select_from(GraphNodeModel)
                .where(GraphNodeModel.workspace_id == workspace_id)
            )
        ).scalar() or 0
        edges = (
            await self.db.execute(
                select(func.count())
                .select_from(GraphEdgeModel)
                .where(GraphEdgeModel.workspace_id == workspace_id)
            )
        ).scalar() or 0
        conversations = (
            await self.db.execute(
                select(func.count())
                .select_from(ConversationModel)
                .where(ConversationModel.workspace_id == workspace_id)
            )
        ).scalar() or 0
        agents = (
            await self.db.execute(
                select(func.count())
                .select_from(AgentConfigModel)
                .where(AgentConfigModel.workspace_id == workspace_id)
            )
        ).scalar() or 0

        return WorkspaceStatsRecord(
            nodes=int(nodes),
            edges=int(edges),
            conversations=int(conversations),
            agents=int(agents),
        )

    async def list_workspace_members(self, workspace_id: str) -> list[WorkspaceMemberRecord]:
        query = text(
            """
            SELECT
                wm.id, wm.workspace_id, wm.user_id, wm.role, wm.created_at,
                u.email, u.name
            FROM workspace_members wm
            JOIN users u ON wm.user_id = u.id
            WHERE wm.workspace_id = :workspace_id
            ORDER BY wm.created_at
            """
        )
        result = await self.db.execute(query, {"workspace_id": workspace_id})
        return [
            WorkspaceMemberRecord(
                id=row.id,
                workspace_id=row.workspace_id,
                user_id=row.user_id,
                role=row.role,
                email=row.email,
                name=row.name,
                created_at=row.created_at,
            )
            for row in result.fetchall()
        ]

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserRecord(id=user.id, email=user.email)

    async def is_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(WorkspaceMemberModel.id).where(
                (WorkspaceMemberModel.workspace_id == workspace_id)
                & (WorkspaceMemberModel.user_id == user_id)
            )
        )
        return result.scalar_one_or_none() is not None

    async def add_workspace_member(
        self, workspace_id: str, user_id: str, role: str
    ) -> WorkspaceMemberRecord:
        member = WorkspaceMemberModel(
            id=str(uuid4()),
            workspace_id=workspace_id,
            user_id=user_id,
            role=role,
        )
        self.db.add(member)
        await self.db.commit()
        return WorkspaceMemberRecord(
            id=member.id,
            workspace_id=member.workspace_id,
            user_id=member.user_id,
            role=member.role,
            created_at=member.created_at,
        )

    async def remove_workspace_member(self, workspace_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(WorkspaceMemberModel).where(
                (WorkspaceMemberModel.workspace_id == workspace_id)
                & (WorkspaceMemberModel.user_id == user_id)
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            return False
        await self.db.delete(member)
        await self.db.commit()
        return True

    async def update_workspace_member_role(
        self, workspace_id: str, user_id: str, role: str
    ) -> bool:
        result = await self.db.execute(
            select(WorkspaceMemberModel).where(
                (WorkspaceMemberModel.workspace_id == workspace_id)
                & (WorkspaceMemberModel.user_id == user_id)
            )
        )
        member = result.scalar_one_or_none()
        if member is None:
            return False
        member.role = role
        await self.db.commit()
        return True

    async def list_inference_servers(self, workspace_id: str) -> list[InferenceServerRecord]:
        result = await self.db.execute(
            select(InferenceServerModel)
            .where(InferenceServerModel.workspace_id == workspace_id)
            .order_by(InferenceServerModel.created_at.desc())
        )
        return [self._to_inference_server_record(server) for server in result.scalars().all()]

    async def create_inference_server(
        self, server: InferenceServerCreateInput
    ) -> InferenceServerRecord:
        now = datetime.now(UTC).replace(tzinfo=None)
        model = InferenceServerModel(
            id=server.id,
            workspace_id=server.workspace_id,
            name=server.name,
            type=server.type,
            endpoint=server.endpoint,
            description=server.description,
            enabled=server.enabled,
            api_key=server.api_key,
            health_path=server.health_path,
            models_path=server.models_path,
            created_at=now,
            updated_at=now,
        )
        self.db.add(model)
        await self.db.commit()
        await self.db.refresh(model)
        return self._to_inference_server_record(model)

    async def update_inference_server(
        self, workspace_id: str, server_id: str, updates: InferenceServerUpdateInput
    ) -> InferenceServerRecord | None:
        result = await self.db.execute(
            select(InferenceServerModel).where(
                (InferenceServerModel.id == server_id)
                & (InferenceServerModel.workspace_id == workspace_id)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return None

        if updates.name is not None:
            model.name = updates.name
        if updates.endpoint is not None:
            model.endpoint = updates.endpoint
        if updates.description is not None:
            model.description = updates.description
        if updates.enabled is not None:
            model.enabled = updates.enabled
        if updates.api_key is not None:
            model.api_key = updates.api_key
        if updates.health_path is not None:
            model.health_path = updates.health_path
        if updates.models_path is not None:
            model.models_path = updates.models_path
        model.updated_at = datetime.now(UTC).replace(tzinfo=None)

        await self.db.commit()
        await self.db.refresh(model)
        return self._to_inference_server_record(model)

    async def delete_inference_server(self, workspace_id: str, server_id: str) -> bool:
        result = await self.db.execute(
            select(InferenceServerModel).where(
                (InferenceServerModel.id == server_id)
                & (InferenceServerModel.workspace_id == workspace_id)
            )
        )
        model = result.scalar_one_or_none()
        if model is None:
            return False
        await self.db.delete(model)
        await self.db.commit()
        return True

    async def set_workspace_logo(self, workspace_id: str, logo_url: str) -> WorkspaceRecord | None:
        result = await self.db.execute(
            select(WorkspaceModel).where(WorkspaceModel.id == workspace_id)
        )
        workspace = result.scalar_one_or_none()
        if workspace is None:
            return None
        workspace.logo_url = logo_url
        workspace.updated_at = datetime.now(UTC).replace(tzinfo=None)
        await self.db.commit()
        await self.db.refresh(workspace)
        return self._to_workspace_record(workspace)
