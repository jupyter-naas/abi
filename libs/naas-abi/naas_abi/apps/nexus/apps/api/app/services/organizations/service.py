from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationMemberRecord,
    OrganizationPermissionPort,
    OrganizationRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceRecord,
)


@dataclass
class OrganizationPermissionError(PermissionError):
    org_id: str
    user_id: str

    def __str__(self) -> str:
        return "organization_access_denied"


@dataclass
class OrganizationSlugAlreadyExistsError(ValueError):
    slug: str

    def __str__(self) -> str:
        return f"organization_slug_exists:{self.slug}"


@dataclass
class OrganizationMemberAlreadyExistsError(ValueError):
    org_id: str
    user_id: str

    def __str__(self) -> str:
        return "organization_member_already_exists"


@dataclass
class OrganizationDomainAlreadyExistsError(ValueError):
    domain: str

    def __str__(self) -> str:
        return "organization_domain_already_exists"


class OrganizationService:
    def __init__(self, adapter: OrganizationPermissionPort):
        self.adapter = adapter

    async def get_organization_role(self, user_id: str, org_id: str) -> str | None:
        return await self.adapter.get_organization_role(user_id=user_id, org_id=org_id)

    async def require_organization_access(self, user_id: str, org_id: str) -> str:
        role = await self.get_organization_role(user_id=user_id, org_id=org_id)
        if role is None:
            raise OrganizationPermissionError(org_id=org_id, user_id=user_id)
        return role

    async def list_organizations(self, user_id: str) -> list[OrganizationRecord]:
        return await self.adapter.list_organizations_for_user(user_id=user_id)

    async def get_organization(self, org_id: str) -> OrganizationRecord | None:
        return await self.adapter.get_organization_by_id(org_id=org_id)

    async def get_organization_by_slug(self, slug: str) -> OrganizationRecord | None:
        return await self.adapter.get_organization_by_slug(slug=slug)

    async def create_organization(
        self,
        *,
        name: str,
        slug: str,
        owner_id: str,
        now: datetime,
        logo_url: str | None = None,
        logo_rectangle_url: str | None = None,
        logo_emoji: str | None = None,
        primary_color: str | None = "#22c55e",
        accent_color: str | None = None,
        background_color: str | None = None,
        font_family: str | None = None,
        font_url: str | None = None,
        login_card_max_width: str | None = None,
        login_card_padding: str | None = None,
        login_card_color: str | None = None,
        login_text_color: str | None = None,
        login_input_color: str | None = None,
        login_border_radius: str | None = None,
        login_bg_image_url: str | None = None,
        show_terms_footer: bool = True,
        show_powered_by: bool = True,
        login_footer_text: str | None = None,
        secondary_logo_url: str | None = None,
        show_logo_separator: bool = False,
        default_theme: str | None = None,
    ) -> OrganizationRecord:
        if await self.adapter.organization_slug_exists(slug=slug):
            raise OrganizationSlugAlreadyExistsError(slug=slug)

        org_id = f"org-{uuid4().hex[:12]}"
        record = await self.adapter.create_organization(
            OrganizationCreateInput(
                id=org_id,
                name=name,
                slug=slug,
                owner_id=owner_id,
                logo_url=logo_url,
                logo_rectangle_url=logo_rectangle_url,
                logo_emoji=logo_emoji,
                primary_color=primary_color,
                accent_color=accent_color,
                background_color=background_color,
                font_family=font_family,
                font_url=font_url,
                login_card_max_width=login_card_max_width,
                login_card_padding=login_card_padding,
                login_card_color=login_card_color,
                login_text_color=login_text_color,
                login_input_color=login_input_color,
                login_border_radius=login_border_radius,
                login_bg_image_url=login_bg_image_url,
                show_terms_footer=show_terms_footer,
                show_powered_by=show_powered_by,
                login_footer_text=login_footer_text,
                secondary_logo_url=secondary_logo_url,
                show_logo_separator=show_logo_separator,
                default_theme=default_theme,
                created_at=now,
                updated_at=now,
            )
        )
        await self.adapter.add_organization_member(
            org_id=record.id,
            user_id=owner_id,
            role="owner",
            created_at=now,
        )
        return record

    async def update_organization(
        self,
        org_id: str,
        updates: OrganizationUpdateInput,
    ) -> OrganizationRecord | None:
        return await self.adapter.update_organization(org_id=org_id, updates=updates)

    async def list_workspaces(self, org_id: str, user_id: str) -> list[OrganizationWorkspaceRecord]:
        return await self.adapter.list_workspaces_for_org_and_user(org_id=org_id, user_id=user_id)

    async def list_members(self, org_id: str) -> list[OrganizationMemberRecord]:
        return await self.adapter.list_organization_members(org_id=org_id)

    async def invite_member(
        self,
        org_id: str,
        email: str,
        role: str,
        now: datetime,
    ) -> OrganizationMemberRecord | None:
        user = await self.adapter.get_user_by_email(email=email)
        if user is None:
            return None
        if await self.adapter.is_organization_member(org_id=org_id, user_id=user.id):
            raise OrganizationMemberAlreadyExistsError(org_id=org_id, user_id=user.id)
        return await self.adapter.add_organization_member(
            org_id=org_id,
            user_id=user.id,
            role=role,
            created_at=now,
        )

    async def update_member_role(
        self,
        org_id: str,
        user_id: str,
        role: str,
    ) -> OrganizationMemberRecord | None:
        return await self.adapter.update_organization_member_role(
            org_id=org_id,
            user_id=user_id,
            role=role,
        )

    async def remove_member(self, org_id: str, user_id: str) -> bool:
        member = await self.adapter.get_organization_member(org_id=org_id, user_id=user_id)
        if member is None or member.role == "owner":
            return False
        return await self.adapter.delete_organization_member(org_id=org_id, user_id=user_id)

    async def list_domains(self, org_id: str) -> list[OrganizationDomainRecord]:
        return await self.adapter.list_organization_domains(org_id=org_id)

    async def add_domain(
        self,
        org_id: str,
        domain: str,
        now: datetime,
        verification_token: str,
    ) -> OrganizationDomainRecord:
        if await self.adapter.domain_exists(domain=domain):
            raise OrganizationDomainAlreadyExistsError(domain=domain)
        return await self.adapter.create_organization_domain(
            OrganizationDomainCreateInput(
                id=str(uuid4()),
                organization_id=org_id,
                domain=domain,
                verification_token=verification_token,
                created_at=now,
            )
        )

    async def verify_domain(
        self,
        org_id: str,
        domain_id: str,
        verified_at: datetime,
    ) -> OrganizationDomainRecord | None:
        return await self.adapter.verify_organization_domain(
            org_id=org_id,
            domain_id=domain_id,
            verified_at=verified_at,
        )

    async def get_domain(self, org_id: str, domain_id: str) -> OrganizationDomainRecord | None:
        return await self.adapter.get_organization_domain(org_id=org_id, domain_id=domain_id)

    async def delete_domain(self, org_id: str, domain_id: str) -> bool:
        return await self.adapter.delete_organization_domain(org_id=org_id, domain_id=domain_id)
