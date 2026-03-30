from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationDomainModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceMemberModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationMemberRecord,
    OrganizationPermissionPort,
    OrganizationRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceRecord,
    UserRecord,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

AsyncSessionGetter = Callable[[], AsyncSession | None]


class OrganizationSecondaryAdapterPostgres(OrganizationPermissionPort):
    def __init__(self, db: AsyncSession | None = None, db_getter: AsyncSessionGetter | None = None):
        self._db = db
        self._db_getter = db_getter

    @property
    def db(self) -> AsyncSession:
        if self._db is not None:
            return self._db
        if self._db_getter is None:
            raise RuntimeError("OrganizationSecondaryAdapterPostgres has no database binding")
        db = self._db_getter()
        if db is None:
            raise RuntimeError("No database session bound in ServiceRegistry context")
        return db

    async def get_organization_role(self, user_id: str, org_id: str) -> str | None:
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

    @staticmethod
    def _to_organization_record(row: OrganizationModel) -> OrganizationRecord:
        return OrganizationRecord(
            id=row.id,
            name=row.name,
            slug=row.slug,
            owner_id=row.owner_id,
            logo_url=row.logo_url,
            logo_rectangle_url=row.logo_rectangle_url,
            logo_emoji=row.logo_emoji,
            primary_color=row.primary_color,
            accent_color=row.accent_color,
            background_color=row.background_color,
            font_family=row.font_family,
            font_url=row.font_url,
            login_card_max_width=row.login_card_max_width,
            login_card_padding=row.login_card_padding,
            login_card_color=row.login_card_color,
            login_text_color=row.login_text_color,
            login_input_color=row.login_input_color,
            login_border_radius=row.login_border_radius,
            login_bg_image_url=row.login_bg_image_url,
            show_terms_footer=row.show_terms_footer,
            show_powered_by=row.show_powered_by,
            login_footer_text=row.login_footer_text,
            secondary_logo_url=row.secondary_logo_url,
            show_logo_separator=row.show_logo_separator,
            default_theme=row.default_theme,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def list_organizations_for_user(self, user_id: str) -> list[OrganizationRecord]:
        result = await self.db.execute(
            select(OrganizationModel)
            .outerjoin(
                OrganizationMemberModel,
                OrganizationModel.id == OrganizationMemberModel.organization_id,
            )
            .where(
                (OrganizationModel.owner_id == user_id)
                | (OrganizationMemberModel.user_id == user_id)
            )
            .distinct()
            .order_by(OrganizationModel.name)
        )
        return [self._to_organization_record(row) for row in result.scalars().all()]

    async def get_organization_by_id(self, org_id: str) -> OrganizationRecord | None:
        result = await self.db.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_organization_record(row)

    async def get_organization_by_slug(self, slug: str) -> OrganizationRecord | None:
        result = await self.db.execute(
            select(OrganizationModel).where(OrganizationModel.slug == slug)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_organization_record(row)

    async def organization_slug_exists(self, slug: str) -> bool:
        result = await self.db.execute(
            select(OrganizationModel.id).where(OrganizationModel.slug == slug)
        )
        return result.scalar_one_or_none() is not None

    async def create_organization(
        self, organization: OrganizationCreateInput
    ) -> OrganizationRecord:
        row = OrganizationModel(
            id=organization.id,
            name=organization.name,
            slug=organization.slug,
            owner_id=organization.owner_id,
            logo_url=organization.logo_url,
            logo_rectangle_url=organization.logo_rectangle_url,
            logo_emoji=organization.logo_emoji,
            primary_color=organization.primary_color,
            accent_color=organization.accent_color,
            background_color=organization.background_color,
            font_family=organization.font_family,
            font_url=organization.font_url,
            login_card_max_width=organization.login_card_max_width,
            login_card_padding=organization.login_card_padding,
            login_card_color=organization.login_card_color,
            login_text_color=organization.login_text_color,
            login_input_color=organization.login_input_color,
            login_border_radius=organization.login_border_radius,
            login_bg_image_url=organization.login_bg_image_url,
            show_terms_footer=organization.show_terms_footer,
            show_powered_by=organization.show_powered_by,
            login_footer_text=organization.login_footer_text,
            secondary_logo_url=organization.secondary_logo_url,
            show_logo_separator=organization.show_logo_separator,
            default_theme=organization.default_theme,
            created_at=organization.created_at,
            updated_at=organization.updated_at,
        )
        self.db.add(row)
        await self.db.flush()
        return self._to_organization_record(row)

    async def update_organization(
        self, org_id: str, updates: OrganizationUpdateInput
    ) -> OrganizationRecord | None:
        result = await self.db.execute(
            select(OrganizationModel).where(OrganizationModel.id == org_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None

        update_data = updates.__dict__.copy()
        set_fields = update_data.pop("set_fields", None)
        if set_fields:
            for field in set_fields:
                setattr(row, field, update_data[field])
        else:
            for field, value in update_data.items():
                if value is not None:
                    setattr(row, field, value)
        await self.db.flush()
        return self._to_organization_record(row)

    async def list_workspaces_for_org_and_user(
        self, org_id: str, user_id: str
    ) -> list[OrganizationWorkspaceRecord]:
        result = await self.db.execute(
            select(WorkspaceModel)
            .outerjoin(WorkspaceMemberModel, WorkspaceModel.id == WorkspaceMemberModel.workspace_id)
            .where(
                (WorkspaceModel.organization_id == org_id)
                & ((WorkspaceModel.owner_id == user_id) | (WorkspaceMemberModel.user_id == user_id))
            )
            .distinct()
            .order_by(WorkspaceModel.name)
        )
        return [
            OrganizationWorkspaceRecord(
                id=row.id,
                name=row.name,
                slug=row.slug,
                owner_id=row.owner_id,
                organization_id=row.organization_id,
                created_at=row.created_at,
                updated_at=row.updated_at,
                logo_url=row.logo_url,
                logo_emoji=row.logo_emoji,
            )
            for row in result.scalars().all()
        ]

    async def list_organization_members(self, org_id: str) -> list[OrganizationMemberRecord]:
        result = await self.db.execute(
            select(OrganizationMemberModel, UserModel)
            .join(UserModel, OrganizationMemberModel.user_id == UserModel.id)
            .where(OrganizationMemberModel.organization_id == org_id)
            .order_by(OrganizationMemberModel.created_at)
        )
        return [
            OrganizationMemberRecord(
                id=member.id,
                organization_id=member.organization_id,
                user_id=member.user_id,
                role=member.role,
                email=user.email,
                name=user.name,
                created_at=member.created_at,
            )
            for member, user in result.all()
        ]

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        result = await self.db.execute(select(UserModel).where(UserModel.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserRecord(id=user.id, email=user.email, name=user.name)

    async def is_organization_member(self, org_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(OrganizationMemberModel.id)
            .where(OrganizationMemberModel.organization_id == org_id)
            .where(OrganizationMemberModel.user_id == user_id)
        )
        return result.scalar_one_or_none() is not None

    async def add_organization_member(
        self, org_id: str, user_id: str, role: str, created_at: datetime
    ) -> OrganizationMemberRecord:
        row = OrganizationMemberModel(
            id=str(uuid4()),
            organization_id=org_id,
            user_id=user_id,
            role=role,
            created_at=created_at,
        )
        self.db.add(row)
        await self.db.flush()
        user_result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = user_result.scalar_one_or_none()
        return OrganizationMemberRecord(
            id=row.id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            role=row.role,
            email=user.email if user else None,
            name=user.name if user else None,
            created_at=row.created_at,
        )

    async def get_organization_member(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberRecord | None:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(
                (OrganizationMemberModel.organization_id == org_id)
                & (OrganizationMemberModel.user_id == user_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        user_result = await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        user = user_result.scalar_one_or_none()
        return OrganizationMemberRecord(
            id=row.id,
            organization_id=row.organization_id,
            user_id=row.user_id,
            role=row.role,
            email=user.email if user else None,
            name=user.name if user else None,
            created_at=row.created_at,
        )

    async def update_organization_member_role(
        self, org_id: str, user_id: str, role: str
    ) -> OrganizationMemberRecord | None:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(
                (OrganizationMemberModel.organization_id == org_id)
                & (OrganizationMemberModel.user_id == user_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.role = role
        await self.db.flush()
        return await self.get_organization_member(org_id=org_id, user_id=user_id)

    async def delete_organization_member(self, org_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(
                (OrganizationMemberModel.organization_id == org_id)
                & (OrganizationMemberModel.user_id == user_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

    async def list_organization_domains(self, org_id: str) -> list[OrganizationDomainRecord]:
        result = await self.db.execute(
            select(OrganizationDomainModel)
            .where(OrganizationDomainModel.organization_id == org_id)
            .order_by(OrganizationDomainModel.created_at)
        )
        return [
            OrganizationDomainRecord(
                id=row.id,
                organization_id=row.organization_id,
                domain=row.domain,
                is_verified=row.is_verified,
                verification_token=row.verification_token,
                created_at=row.created_at,
                verified_at=row.verified_at,
            )
            for row in result.scalars().all()
        ]

    async def domain_exists(self, domain: str) -> bool:
        result = await self.db.execute(
            select(OrganizationDomainModel.id).where(OrganizationDomainModel.domain == domain)
        )
        return result.scalar_one_or_none() is not None

    async def create_organization_domain(
        self, domain: OrganizationDomainCreateInput
    ) -> OrganizationDomainRecord:
        row = OrganizationDomainModel(
            id=domain.id,
            organization_id=domain.organization_id,
            domain=domain.domain,
            is_verified=False,
            verification_token=domain.verification_token,
            created_at=domain.created_at,
        )
        self.db.add(row)
        await self.db.flush()
        return OrganizationDomainRecord(
            id=row.id,
            organization_id=row.organization_id,
            domain=row.domain,
            is_verified=row.is_verified,
            verification_token=row.verification_token,
            created_at=row.created_at,
            verified_at=row.verified_at,
        )

    async def get_organization_domain(
        self, org_id: str, domain_id: str
    ) -> OrganizationDomainRecord | None:
        result = await self.db.execute(
            select(OrganizationDomainModel).where(
                (OrganizationDomainModel.id == domain_id)
                & (OrganizationDomainModel.organization_id == org_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return OrganizationDomainRecord(
            id=row.id,
            organization_id=row.organization_id,
            domain=row.domain,
            is_verified=row.is_verified,
            verification_token=row.verification_token,
            created_at=row.created_at,
            verified_at=row.verified_at,
        )

    async def verify_organization_domain(
        self, org_id: str, domain_id: str, verified_at: datetime
    ) -> OrganizationDomainRecord | None:
        result = await self.db.execute(
            select(OrganizationDomainModel).where(
                (OrganizationDomainModel.id == domain_id)
                & (OrganizationDomainModel.organization_id == org_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        row.is_verified = True
        row.verification_token = None
        row.verified_at = verified_at
        await self.db.flush()
        return OrganizationDomainRecord(
            id=row.id,
            organization_id=row.organization_id,
            domain=row.domain,
            is_verified=row.is_verified,
            verification_token=row.verification_token,
            created_at=row.created_at,
            verified_at=row.verified_at,
        )

    async def delete_organization_domain(self, org_id: str, domain_id: str) -> bool:
        result = await self.db.execute(
            select(OrganizationDomainModel).where(
                (OrganizationDomainModel.id == domain_id)
                & (OrganizationDomainModel.organization_id == org_id)
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True
