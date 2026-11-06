"""``ViewStore`` on Nexus's database (PostgreSQL or SQLite): ``view_as_views``
(migration 0069), and the rows of ``users``, ``auth_sessions``, ``workspaces`` and
``organizations`` a view reads."""

from __future__ import annotations

import json
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import (
    AuthSessionModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.view_as.port import (
    Person,
    RecordedGroups,
    ViewRecord,
    ViewStore,
    WorkspaceRef,
)
from sqlalchemy import (
    Column,
    DateTime,
    MetaData,
    String,
    Table,
    Text,
    insert,
    or_,
    select,
    update,
)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

VIEWS = Table(
    "view_as_views",
    MetaData(),
    Column("session_id", String(64), primary_key=True),
    Column("viewer_id", String(255), nullable=False),
    Column("person_id", String(255), nullable=False),
    Column("person_principal_id", String(255), nullable=False),
    Column("person_name", String(255), nullable=False),
    Column("workspace_id", String(255), nullable=False),
    Column("workspace_name", String(255), nullable=False),
    Column("container", String(512), nullable=False),
    Column("group_ids", Text, nullable=False),
    Column("groups_from", DateTime(timezone=False), nullable=True),
    Column("started_at", DateTime(timezone=False), nullable=False),
    Column("ends_at", DateTime(timezone=False), nullable=False),
    Column("ended_at", DateTime(timezone=False), nullable=True),
)


def _groups(raw: str | None) -> tuple[str, ...]:
    try:
        return tuple(str(g) for g in json.loads(raw or "[]"))
    except ValueError:
        return ()


def _record(row) -> ViewRecord:
    return ViewRecord(
        session_id=row.session_id,
        viewer_id=row.viewer_id,
        person_id=row.person_id,
        person_principal_id=row.person_principal_id,
        person_name=row.person_name,
        workspace_id=row.workspace_id,
        workspace_name=row.workspace_name,
        container=row.container,
        group_ids=_groups(row.group_ids),
        groups_from=row.groups_from,
        started_at=row.started_at,
        ends_at=row.ends_at,
        ended_at=row.ended_at,
    )


class ViewAsSecondaryAdapterSql(ViewStore):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get(self, session_id: str) -> ViewRecord | None:
        row = (await self.db.execute(select(VIEWS).where(VIEWS.c.session_id == session_id))).first()
        return _record(row) if row is not None else None

    async def begin(self, record: ViewRecord) -> bool:
        values = {
            "session_id": record.session_id,
            "viewer_id": record.viewer_id,
            "person_id": record.person_id,
            "person_principal_id": record.person_principal_id,
            "person_name": record.person_name,
            "workspace_id": record.workspace_id,
            "workspace_name": record.workspace_name,
            "container": record.container,
            "group_ids": json.dumps(list(record.group_ids)),
            "groups_from": record.groups_from,
            "started_at": record.started_at,
            "ends_at": record.ends_at,
            "ended_at": None,
        }
        # An ended view is replaced by the new one, atomically: the statement alone
        # decides, so two starts of one session cannot both win.
        replaced = await self.db.execute(
            update(VIEWS)
            .where(VIEWS.c.session_id == record.session_id, VIEWS.c.ended_at.is_not(None))
            .values(**values)
        )
        if replaced.rowcount:
            return True
        try:
            async with self.db.begin_nested():
                await self.db.execute(insert(VIEWS).values(**values))
        except IntegrityError:
            return False  # a view of this session has not ended
        return True

    async def end(self, session_id: str, at: datetime) -> bool:
        ended = await self.db.execute(
            update(VIEWS)
            .where(VIEWS.c.session_id == session_id, VIEWS.c.ended_at.is_(None))
            .values(ended_at=at)
        )
        return bool(ended.rowcount)

    async def person(self, principal_id: str) -> Person | None:
        row = (
            await self.db.execute(
                select(UserModel.id, UserModel.principal_id, UserModel.name).where(
                    or_(UserModel.principal_id == principal_id, UserModel.id == principal_id),
                    UserModel.deleted_at.is_(None),
                )
            )
        ).first()
        if row is None:
            return None
        return Person(user_id=row.id, principal_id=row.principal_id or row.id, name=row.name)

    async def recorded_groups(self, user_id: str) -> RecordedGroups | None:
        row = (
            await self.db.execute(
                select(AuthSessionModel.group_ids, AuthSessionModel.created_at)
                .where(AuthSessionModel.user_id == user_id)
                .order_by(AuthSessionModel.created_at.desc())
                .limit(1)
            )
        ).first()
        if row is None:
            return None
        return RecordedGroups(group_ids=_groups(row.group_ids), at=row.created_at)

    async def workspaces(self, ids: list[str]) -> list[WorkspaceRef]:
        if not ids:
            return []
        rows = (
            await self.db.execute(
                select(
                    WorkspaceModel.id,
                    WorkspaceModel.name,
                    WorkspaceModel.organization_id,
                    OrganizationModel.name.label("organization_name"),
                )
                .outerjoin(
                    OrganizationModel, OrganizationModel.id == WorkspaceModel.organization_id
                )
                .where(WorkspaceModel.id.in_(ids))
                .order_by(WorkspaceModel.name, WorkspaceModel.id)
            )
        ).all()
        return [
            WorkspaceRef(
                id=row.id,
                name=row.name,
                organization_id=row.organization_id,
                organization_name=row.organization_name,
            )
            for row in rows
        ]

    async def commit(self) -> None:
        await self.db.commit()
