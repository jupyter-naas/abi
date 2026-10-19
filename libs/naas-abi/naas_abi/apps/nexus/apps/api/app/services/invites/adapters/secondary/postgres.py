"""``InvitationPersistencePort`` on Nexus's database (PostgreSQL or SQLite)."""

from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import (
    InvitationModel,
    OrganizationDomainModel,
    OrganizationMemberModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    Invitation,
    InvitationPersistencePort,
    InvitationStatus,
)
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession


def _grants(raw: str | None) -> tuple[str, ...]:
    try:
        return tuple(str(i) for i in json.loads(raw or "[]"))
    except ValueError:
        return ()


def _invitation(model: InvitationModel) -> Invitation:
    return Invitation(
        id=model.id,
        email=model.email,
        provider=model.provider,
        organization_id=model.organization_id,
        org_role=model.org_role,
        workspace_id=model.workspace_id,
        workspace_role=model.workspace_role,
        invited_by=model.invited_by,
        grant_ids=_grants(model.grant_ids),
        status=model.status,  # type: ignore[arg-type]
        created_at=model.created_at,
        accepted_at=model.accepted_at,
        accepted_user_id=model.accepted_user_id,
    )


class InvitationSecondaryAdapterPostgres(InvitationPersistencePort):
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def add(self, invitation: Invitation, *, now: datetime) -> Invitation:
        self.db.add(
            InvitationModel(
                id=invitation.id,
                email=invitation.email,
                provider=invitation.provider,
                organization_id=invitation.organization_id,
                org_role=invitation.org_role,
                workspace_id=invitation.workspace_id,
                workspace_role=invitation.workspace_role,
                invited_by=invitation.invited_by,
                grant_ids=json.dumps(list(invitation.grant_ids)),
                status="pending",
                created_at=now,
                updated_at=now,
            )
        )
        await self.db.flush()
        return await self._get(invitation.id)

    async def _get(self, invitation_id: str) -> Invitation:
        found = await self.get(invitation_id)
        assert found is not None
        return found

    async def get(self, invitation_id: str) -> Invitation | None:
        model = await self.db.get(InvitationModel, invitation_id)
        if model is not None:
            await self.db.refresh(model)
        return _invitation(model) if model is not None else None

    async def find_pending(
        self,
        *,
        email: str,
        provider: str,
        organization_id: str | None,
        workspace_id: str | None,
    ) -> Invitation | None:
        query = select(InvitationModel).where(
            InvitationModel.email == email,
            InvitationModel.provider == provider,
            InvitationModel.status == "pending",
            InvitationModel.organization_id.is_(None)
            if organization_id is None
            else InvitationModel.organization_id == organization_id,
            InvitationModel.workspace_id.is_(None)
            if workspace_id is None
            else InvitationModel.workspace_id == workspace_id,
        )
        model = (await self.db.execute(query)).scalars().first()
        return _invitation(model) if model is not None else None

    async def list(
        self,
        *,
        organization_id: str | None = None,
        workspace_id: str | None = None,
        status: InvitationStatus | None = "pending",
    ) -> list[Invitation]:
        query = select(InvitationModel).order_by(InvitationModel.created_at.desc())
        if organization_id is not None:
            query = query.where(InvitationModel.organization_id == organization_id)
        if workspace_id is not None:
            query = query.where(InvitationModel.workspace_id == workspace_id)
        if status is not None:
            query = query.where(InvitationModel.status == status)
        return [_invitation(m) for m in (await self.db.execute(query)).scalars()]

    async def pending_for(self, *, email: str, provider: str) -> list[Invitation]:
        query = (
            select(InvitationModel)
            .where(
                InvitationModel.email == email,
                InvitationModel.provider == provider,
                InvitationModel.status == "pending",
            )
            .order_by(InvitationModel.created_at)
        )
        return [_invitation(m) for m in (await self.db.execute(query)).scalars()]

    async def update(
        self,
        invitation_id: str,
        *,
        org_role: str | None,
        workspace_role: str | None,
        grant_ids: Sequence[str],
        invited_by: str | None,
        now: datetime,
    ) -> Invitation:
        await self.db.execute(
            update(InvitationModel)
            .where(InvitationModel.id == invitation_id)
            .values(
                org_role=org_role,
                workspace_role=workspace_role,
                grant_ids=json.dumps(list(grant_ids)),
                invited_by=invited_by,
                updated_at=now,
            )
        )
        await self.db.flush()
        return await self._get(invitation_id)

    async def _transition(self, invitation_id: str, **values: object) -> bool:
        """Pending to something else, once: whoever changes the row first wins."""
        result = await self.db.execute(
            update(InvitationModel)
            .where(InvitationModel.id == invitation_id, InvitationModel.status == "pending")
            .values(**values)
        )
        await self.db.flush()
        return result.rowcount > 0  # type: ignore[attr-defined,no-any-return]

    async def mark_accepted(self, invitation_id: str, *, user_id: str, now: datetime) -> bool:
        return await self._transition(
            invitation_id,
            status="accepted",
            accepted_at=now,
            accepted_user_id=user_id,
            updated_at=now,
        )

    async def mark_revoked(self, invitation_id: str, *, now: datetime) -> bool:
        return await self._transition(invitation_id, status="revoked", updated_at=now)

    async def provider_for_domain(self, domain: str, organization_id: str | None) -> str | None:
        return (
            await self.db.execute(
                select(OrganizationDomainModel.provider).where(
                    func.lower(OrganizationDomainModel.domain) == domain.lower(),
                    OrganizationDomainModel.is_verified.is_(True),
                    OrganizationDomainModel.provider.is_not(None),
                )
            )
        ).scalar_one_or_none()

    async def organization_of_workspace(self, workspace_id: str) -> str | None:
        return (
            await self.db.execute(
                select(WorkspaceModel.organization_id).where(WorkspaceModel.id == workspace_id)
            )
        ).scalar_one_or_none()

    async def user_id_by_email(self, email: str) -> str | None:
        return (
            await self.db.execute(select(UserModel.id).where(UserModel.email == email.lower()))
        ).scalar_one_or_none()

    async def add_membership(
        self,
        *,
        user_id: str,
        organization_id: str | None,
        org_role: str | None,
        workspace_id: str | None,
        workspace_role: str | None,
        now: datetime,
    ) -> None:
        if organization_id and org_role:
            held = (
                await self.db.execute(
                    select(OrganizationMemberModel.id).where(
                        OrganizationMemberModel.organization_id == organization_id,
                        OrganizationMemberModel.user_id == user_id,
                    )
                )
            ).first()
            if held is None:
                self.db.add(
                    OrganizationMemberModel(
                        id=str(uuid4()),
                        organization_id=organization_id,
                        user_id=user_id,
                        role=org_role,
                        created_at=now,
                    )
                )
        if workspace_id and workspace_role:
            held = (
                await self.db.execute(
                    select(WorkspaceMemberModel.id).where(
                        WorkspaceMemberModel.workspace_id == workspace_id,
                        WorkspaceMemberModel.user_id == user_id,
                    )
                )
            ).first()
            if held is None:
                self.db.add(
                    WorkspaceMemberModel(
                        id=str(uuid4()),
                        workspace_id=workspace_id,
                        user_id=user_id,
                        role=workspace_role,
                        created_at=now,
                    )
                )
        await self.db.flush()

    async def commit(self) -> None:
        await self.db.commit()

    async def rollback(self) -> None:
        await self.db.rollback()
