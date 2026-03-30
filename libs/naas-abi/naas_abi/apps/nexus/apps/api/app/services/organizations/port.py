from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class OrganizationRecord:
    id: str
    name: str
    slug: str
    owner_id: str
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = True
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class OrganizationCreateInput:
    id: str
    name: str
    slug: str
    owner_id: str
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = "#22c55e"
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool = True
    show_powered_by: bool = True
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool = False
    default_theme: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class OrganizationUpdateInput:
    name: str | None = None
    slug: str | None = None
    logo_url: str | None = None
    logo_rectangle_url: str | None = None
    logo_emoji: str | None = None
    primary_color: str | None = None
    accent_color: str | None = None
    background_color: str | None = None
    font_family: str | None = None
    font_url: str | None = None
    login_card_max_width: str | None = None
    login_card_padding: str | None = None
    login_card_color: str | None = None
    login_text_color: str | None = None
    login_input_color: str | None = None
    login_border_radius: str | None = None
    login_bg_image_url: str | None = None
    show_terms_footer: bool | None = None
    show_powered_by: bool | None = None
    login_footer_text: str | None = None
    secondary_logo_url: str | None = None
    show_logo_separator: bool | None = None
    default_theme: str | None = None
    updated_at: datetime | None = None
    set_fields: set[str] | None = None


@dataclass
class OrganizationWorkspaceRecord:
    id: str
    name: str
    slug: str
    owner_id: str
    organization_id: str | None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    logo_url: str | None = None
    logo_emoji: str | None = None


@dataclass
class OrganizationMemberRecord:
    id: str
    organization_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None


@dataclass
class UserRecord:
    id: str
    email: str
    name: str | None = None


@dataclass
class OrganizationDomainRecord:
    id: str
    organization_id: str
    domain: str
    is_verified: bool
    verification_token: str | None = None
    created_at: datetime | None = None
    verified_at: datetime | None = None


@dataclass
class OrganizationDomainCreateInput:
    id: str
    organization_id: str
    domain: str
    verification_token: str
    created_at: datetime | None = None


class OrganizationPermissionPort(ABC):
    @abstractmethod
    async def get_organization_role(self, user_id: str, org_id: str) -> str | None:
        raise NotImplementedError

    @abstractmethod
    async def list_organizations_for_user(self, user_id: str) -> list[OrganizationRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_organization_by_id(self, org_id: str) -> OrganizationRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_organization_by_slug(self, slug: str) -> OrganizationRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def organization_slug_exists(self, slug: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_organization(
        self, organization: OrganizationCreateInput
    ) -> OrganizationRecord:
        raise NotImplementedError

    @abstractmethod
    async def update_organization(
        self, org_id: str, updates: OrganizationUpdateInput
    ) -> OrganizationRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def list_workspaces_for_org_and_user(
        self, org_id: str, user_id: str
    ) -> list[OrganizationWorkspaceRecord]:
        raise NotImplementedError

    @abstractmethod
    async def list_organization_members(self, org_id: str) -> list[OrganizationMemberRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def is_organization_member(self, org_id: str, user_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def add_organization_member(
        self, org_id: str, user_id: str, role: str, created_at: datetime
    ) -> OrganizationMemberRecord:
        raise NotImplementedError

    @abstractmethod
    async def get_organization_member(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def update_organization_member_role(
        self, org_id: str, user_id: str, role: str
    ) -> OrganizationMemberRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def delete_organization_member(self, org_id: str, user_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def list_organization_domains(self, org_id: str) -> list[OrganizationDomainRecord]:
        raise NotImplementedError

    @abstractmethod
    async def domain_exists(self, domain: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def create_organization_domain(
        self, domain: OrganizationDomainCreateInput
    ) -> OrganizationDomainRecord:
        raise NotImplementedError

    @abstractmethod
    async def get_organization_domain(
        self, org_id: str, domain_id: str
    ) -> OrganizationDomainRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def verify_organization_domain(
        self, org_id: str, domain_id: str, verified_at: datetime
    ) -> OrganizationDomainRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def delete_organization_domain(self, org_id: str, domain_id: str) -> bool:
        raise NotImplementedError
