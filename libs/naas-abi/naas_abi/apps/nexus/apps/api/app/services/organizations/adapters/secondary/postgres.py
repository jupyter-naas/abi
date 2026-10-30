from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.datetime_compat import UTC
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationDomainModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationMemberAccountRecord,
    OrganizationMemberProfileRecord,
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

    async def list_all_organizations(self) -> list[OrganizationRecord]:
        result = await self.db.execute(select(OrganizationModel).order_by(OrganizationModel.name))
        return [self._to_organization_record(row) for row in result.scalars().all()]

    async def get_users_by_ids(self, user_ids: list[str]) -> dict[str, UserRecord]:
        if not user_ids:
            return {}
        result = await self.db.execute(select(UserModel).where(UserModel.id.in_(user_ids)))
        return {
            user.id: UserRecord(id=user.id, email=user.email, name=user.name, bio=user.bio)
            for user in result.scalars().all()
        }

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

    async def list_workspaces_for_org(self, org_id: str) -> list[OrganizationWorkspaceRecord]:
        result = await self.db.execute(
            select(WorkspaceModel)
            .where(WorkspaceModel.organization_id == org_id)
            .order_by(WorkspaceModel.name)
        )
        return [self._to_workspace_record(row) for row in result.scalars().all()]

    def _to_workspace_record(self, row: WorkspaceModel) -> OrganizationWorkspaceRecord:
        return OrganizationWorkspaceRecord(
            id=row.id,
            name=row.name,
            slug=row.slug,
            owner_id=row.owner_id,
            organization_id=row.organization_id,
            created_at=row.created_at,
            updated_at=row.updated_at,
            logo_url=row.logo_url,
            logo_emoji=row.logo_emoji,
            workspace_group=row.workspace_group,
        )

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        normalized = email.lower().strip()
        result = await self.db.execute(select(UserModel).where(UserModel.email == normalized))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserRecord(id=user.id, email=user.email, name=user.name, bio=user.bio)

    async def get_member_account(self, user_id: str) -> OrganizationMemberAccountRecord | None:
        user = (
            await self.db.execute(select(UserModel).where(UserModel.id == user_id))
        ).scalar_one_or_none()
        if user is None:
            return None
        return OrganizationMemberAccountRecord(
            user_id=user_id,
            email=user.email,
            name=user.name,
            avatar=user.avatar,
            organization=user.organization,
            job_title=user.job_title,
            bio=user.bio,
            created_at=user.created_at,
            updated_at=user.updated_at,
        )

    @staticmethod
    def _to_profile(row: OrganizationMemberModel) -> OrganizationMemberProfileRecord:
        return OrganizationMemberProfileRecord(
            name=row.name,
            avatar=row.avatar,
            organization=row.organization_name,
            job_title=row.job_title,
            bio=row.bio,
            service_line=row.service_line,
            country=row.country,
            interest=row.interest,
        )

    async def _find_profile_row(self, org_id: str, user_id: str) -> OrganizationMemberModel | None:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(
                (OrganizationMemberModel.organization_id == org_id)
                & (OrganizationMemberModel.user_id == user_id)
            )
        )
        return result.scalar_one_or_none()

    async def _profile_row(self, org_id: str, user_id: str) -> OrganizationMemberModel:
        """The row a member's profile is kept in, made on the first edit. Who holds
        which role is IAM's: ``role`` here is only the column's placeholder."""
        row = await self._find_profile_row(org_id, user_id)
        if row is None:
            row = OrganizationMemberModel(
                id=str(uuid4()),
                organization_id=org_id,
                user_id=user_id,
                role="member",
                created_at=datetime.now(UTC).replace(tzinfo=None),
            )
            self.db.add(row)
        return row

    async def get_organization_member_profile(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberProfileRecord | None:
        row = await self._find_profile_row(org_id, user_id)
        return self._to_profile(row) if row is not None else None

    async def list_organization_member_profiles(
        self, org_id: str
    ) -> dict[str, OrganizationMemberProfileRecord]:
        result = await self.db.execute(
            select(OrganizationMemberModel).where(OrganizationMemberModel.organization_id == org_id)
        )
        return {row.user_id: self._to_profile(row) for row in result.scalars().all()}

    async def update_organization_member_profile(
        self,
        org_id: str,
        user_id: str,
        *,
        name: str | None,
        organization: str | None,
        job_title: str | None,
        bio: str | None,
        service_line: str | None = None,
        country: str | None = None,
        interest: str | None = None,
    ) -> OrganizationMemberProfileRecord:
        row = await self._profile_row(org_id, user_id)
        for field, value in (
            ("name", name),
            ("organization_name", organization),
            ("job_title", job_title),
            ("bio", bio),
            ("service_line", service_line),
            ("country", country),
            ("interest", interest),
        ):
            if value is not None:
                setattr(row, field, value)
        await self.db.flush()
        return self._to_profile(row)

    async def set_organization_member_avatar(
        self, org_id: str, user_id: str, avatar: str | None
    ) -> str | None:
        row = await self._profile_row(org_id, user_id)
        previous = row.avatar
        row.avatar = avatar
        await self.db.flush()
        return previous

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
            provider=row.provider,
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
            provider=row.provider,
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
            provider=row.provider,
        )

    async def set_organization_domain_provider(
        self, org_id: str, domain_id: str, provider: str | None
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
        row.provider = provider
        await self.db.flush()
        return OrganizationDomainRecord(
            id=row.id,
            organization_id=row.organization_id,
            domain=row.domain,
            is_verified=row.is_verified,
            verification_token=row.verification_token,
            created_at=row.created_at,
            verified_at=row.verified_at,
            provider=row.provider,
        )

    async def delete_organization(self, org_id: str) -> bool:
        row = (
            await self.db.execute(select(OrganizationModel).where(OrganizationModel.id == org_id))
        ).scalar_one_or_none()
        if row is None:
            return False
        await self.db.delete(row)
        await self.db.flush()
        return True

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
