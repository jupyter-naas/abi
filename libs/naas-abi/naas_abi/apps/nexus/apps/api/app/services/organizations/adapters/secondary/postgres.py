from __future__ import annotations

import json
from collections.abc import Callable
from datetime import datetime

from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationDomainModel,
    OrganizationModel,
    OrganizationRoleFeaturesModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationPermissionPort,
    OrganizationRecord,
    OrganizationRoleFeaturesRecord,
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
            user.id: UserRecord(id=user.id, email=user.email, name=user.name)
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
        )

    async def get_user_by_email(self, email: str) -> UserRecord | None:
        normalized = email.lower().strip()
        result = await self.db.execute(select(UserModel).where(UserModel.email == normalized))
        user = result.scalar_one_or_none()
        if user is None:
            return None
        return UserRecord(id=user.id, email=user.email, name=user.name)

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

    @staticmethod
    def _decode_role_baseline(raw: str) -> dict[str, list[str]]:
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if not isinstance(parsed, dict):
            return {}
        decoded: dict[str, list[str]] = {}
        for role, features in parsed.items():
            if not isinstance(role, str) or not isinstance(features, list):
                continue
            decoded[role] = [str(feature) for feature in features]
        return decoded

    def _to_role_features_record(
        self, row: OrganizationRoleFeaturesModel
    ) -> OrganizationRoleFeaturesRecord:
        return OrganizationRoleFeaturesRecord(
            organization_id=row.organization_id,
            role_baseline=self._decode_role_baseline(row.role_baseline),
            updated_by=row.updated_by,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    async def get_organization_role_features(
        self, org_id: str
    ) -> OrganizationRoleFeaturesRecord | None:
        result = await self.db.execute(
            select(OrganizationRoleFeaturesModel).where(
                OrganizationRoleFeaturesModel.organization_id == org_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_role_features_record(row)

    async def upsert_organization_role_features(
        self,
        org_id: str,
        role_baseline: dict[str, list[str]],
        updated_by: str | None,
        now: datetime,
    ) -> OrganizationRoleFeaturesRecord:
        payload = json.dumps(
            {role: list(features) for role, features in role_baseline.items()},
            separators=(",", ":"),
            sort_keys=True,
        )
        result = await self.db.execute(
            select(OrganizationRoleFeaturesModel).where(
                OrganizationRoleFeaturesModel.organization_id == org_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            row = OrganizationRoleFeaturesModel(
                organization_id=org_id,
                role_baseline=payload,
                updated_by=updated_by,
                created_at=now,
                updated_at=now,
            )
            self.db.add(row)
        else:
            row.role_baseline = payload
            row.updated_by = updated_by
            row.updated_at = now
        await self.db.flush()
        return self._to_role_features_record(row)
