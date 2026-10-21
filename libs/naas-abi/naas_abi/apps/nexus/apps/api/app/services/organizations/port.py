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
    workspace_group: str | None = None
    # Saved in Organization Settings > Workspaces; None = config overrides apply.
    feature_overrides: dict[str, bool] | None = None


@dataclass
class OrganizationMemberRecord:
    id: str
    organization_id: str
    user_id: str
    role: str
    email: str | None = None
    name: str | None = None
    created_at: datetime | None = None
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    service_line: str | None = None
    country: str | None = None
    interest: str | None = None


@dataclass
class OrganizationMemberAccountRecord:
    """The member's platform account (users row), as the account settings show it."""

    user_id: str
    email: str | None = None
    name: str | None = None
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass
class OrganizationMemberProfileRecord:
    """What this organization set for the member; None falls back to the account."""

    name: str | None = None
    avatar: str | None = None
    organization: str | None = None
    job_title: str | None = None
    bio: str | None = None
    service_line: str | None = None
    country: str | None = None
    interest: str | None = None


@dataclass
class OrganizationMemberDetailsRecord:
    member: OrganizationMemberRecord
    account: OrganizationMemberAccountRecord
    organization_profile: OrganizationMemberProfileRecord


@dataclass
class OrganizationWorkspaceMembershipRecord:
    user_id: str
    workspace_id: str
    role: str


@dataclass
class UserOrganizationMembershipRecord:
    user_id: str
    organization_id: str
    organization_name: str
    role: str


@dataclass
class UserRecord:
    id: str
    email: str
    name: str | None = None
    bio: str | None = None


@dataclass
class OrganizationDomainRecord:
    id: str
    organization_id: str
    domain: str
    is_verified: bool
    verification_token: str | None = None
    created_at: datetime | None = None
    verified_at: datetime | None = None
    # The identity provider a login with an email of this domain goes to.
    provider: str | None = None


@dataclass
class OrganizationDomainCreateInput:
    id: str
    organization_id: str
    domain: str
    verification_token: str
    created_at: datetime | None = None


@dataclass
class OrganizationRoleFeaturesRecord:
    organization_id: str
    role_baseline: dict[str, list[str]]
    updated_by: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class OrganizationPermissionPort(ABC):
    """The organizations Nexus keeps. Who belongs to them and with which role is
    IAM's (``services/iam/memberships``), not this port's."""

    @abstractmethod
    async def list_all_organizations(self) -> list[OrganizationRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_users_by_ids(self, user_ids: list[str]) -> dict[str, UserRecord]:
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
    async def list_workspaces_for_org(self, org_id: str) -> list[OrganizationWorkspaceRecord]:
        raise NotImplementedError

    @abstractmethod
    async def get_user_by_email(self, email: str) -> UserRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def get_member_account(self, user_id: str) -> OrganizationMemberAccountRecord | None:
        """The member's platform account (users row), as the account settings show it."""
        raise NotImplementedError

    @abstractmethod
    async def get_organization_member_profile(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberProfileRecord | None:
        """What this organization set for the member; None when it set nothing."""
        raise NotImplementedError

    @abstractmethod
    async def list_organization_member_profiles(
        self, org_id: str
    ) -> dict[str, OrganizationMemberProfileRecord]:
        """Every member profile this organization set, by user id."""
        raise NotImplementedError

    @abstractmethod
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
        """Set the member's profile in this org (kept from the first edit on);
        ``None`` leaves a field unchanged."""
        raise NotImplementedError

    @abstractmethod
    async def set_organization_member_avatar(
        self, org_id: str, user_id: str, avatar: str | None
    ) -> str | None:
        """Set (or clear, with ``None``) the org avatar; returns the previous org avatar."""
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
    async def delete_organization(self, org_id: str) -> bool:
        """Remove an organization row (a failed create takes its row back)."""
        raise NotImplementedError

    @abstractmethod
    async def delete_organization_domain(self, org_id: str, domain_id: str) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def set_organization_domain_provider(
        self, org_id: str, domain_id: str, provider: str | None
    ) -> OrganizationDomainRecord | None:
        """Route the domain's logins to ``provider`` (None: the default provider)."""
        raise NotImplementedError

    @abstractmethod
    async def get_organization_role_features(
        self, org_id: str
    ) -> OrganizationRoleFeaturesRecord | None:
        raise NotImplementedError

    @abstractmethod
    async def upsert_organization_role_features(
        self,
        org_id: str,
        role_baseline: dict[str, list[str]],
        updated_by: str | None,
        now: datetime,
    ) -> OrganizationRoleFeaturesRecord:
        raise NotImplementedError
