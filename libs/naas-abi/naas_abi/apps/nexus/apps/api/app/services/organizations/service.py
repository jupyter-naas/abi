from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.core.workspace_access import INHERITED_FROM_ORG, max_role
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationMemberDetailsRecord,
    OrganizationMemberRecord,
    OrganizationPermissionPort,
    OrganizationRecord,
    OrganizationRoleFeaturesRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceMembershipRecord,
    OrganizationWorkspaceRecord,
    UserOrganizationMembershipRecord,
)


@dataclass
class MemberWorkspaceAccess:
    workspace_id: str
    name: str
    slug: str
    role: str
    #: "workspace" for an explicit membership or ownership, "organization" when
    #: the org role (owner/admin) gives the higher role.
    source: str


def member_workspace_access(
    *,
    user_id: str,
    organization_role: str,
    workspaces: list[OrganizationWorkspaceRecord],
    memberships: list[OrganizationWorkspaceMembershipRecord],
) -> list[MemberWorkspaceAccess]:
    """The member's effective role on each workspace of the org (see core/workspace_access)."""
    explicit = {m.workspace_id: m.role for m in memberships if m.user_id == user_id}
    inherited = INHERITED_FROM_ORG.get(organization_role)
    access: list[MemberWorkspaceAccess] = []
    for workspace in workspaces:
        own = max_role(explicit.get(workspace.id), "owner" if workspace.owner_id == user_id else None)
        role = max_role(own, inherited)
        if role is None:
            continue
        source = "workspace" if own == role else "organization"
        access.append(
            MemberWorkspaceAccess(
                workspace_id=workspace.id,
                name=workspace.name,
                slug=workspace.slug,
                role=role,
                source=source,
            )
        )
    return access


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


# Roles the platform can grant. Owners come only from the config seed
# (organizations[].owner_email), never from an invite or a role change.
ASSIGNABLE_MEMBER_ROLES = ("admin", "member")


@dataclass
class OrganizationRoleNotAssignableError(ValueError):
    role: str

    def __str__(self) -> str:
        return f"organization_role_not_assignable:{self.role}"


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

    async def list_all_workspaces(self, org_id: str) -> list[OrganizationWorkspaceRecord]:
        return await self.adapter.list_workspaces_for_org(org_id=org_id)

    async def list_workspace_memberships(
        self, org_id: str
    ) -> list[OrganizationWorkspaceMembershipRecord]:
        return await self.adapter.list_workspace_memberships_for_org(org_id=org_id)

    async def list_all_memberships(self) -> list[UserOrganizationMembershipRecord]:
        return await self.adapter.list_all_organization_memberships()

    async def list_members(self, org_id: str) -> list[OrganizationMemberRecord]:
        return await self.adapter.list_organization_members(org_id=org_id)

    async def invite_member(
        self,
        org_id: str,
        email: str,
        role: str,
        now: datetime,
    ) -> OrganizationMemberRecord | None:
        """Attach an existing user by email. Callers that support create-on-invite
        must ensure the user exists (via AuthService.ensure_user_for_invite) first.
        """
        if role not in ASSIGNABLE_MEMBER_ROLES:
            raise OrganizationRoleNotAssignableError(role=role)
        normalized_email = email.lower().strip()
        user = await self.adapter.get_user_by_email(email=normalized_email)
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

    async def get_organization_member(
        self,
        org_id: str,
        user_id: str,
    ) -> OrganizationMemberRecord | None:
        return await self.adapter.get_organization_member(org_id=org_id, user_id=user_id)

    async def update_member_role(
        self,
        org_id: str,
        user_id: str,
        role: str,
    ) -> OrganizationMemberRecord | None:
        if role not in ASSIGNABLE_MEMBER_ROLES:
            raise OrganizationRoleNotAssignableError(role=role)
        return await self.adapter.update_organization_member_role(
            org_id=org_id,
            user_id=user_id,
            role=role,
        )

    async def get_member_details(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberDetailsRecord | None:
        return await self.adapter.get_organization_member_details(org_id=org_id, user_id=user_id)

    async def get_member_workspace_access(
        self, org_id: str, user_id: str, organization_role: str
    ) -> list[MemberWorkspaceAccess]:
        return member_workspace_access(
            user_id=user_id,
            organization_role=organization_role,
            workspaces=await self.list_all_workspaces(org_id=org_id),
            memberships=await self.list_workspace_memberships(org_id=org_id),
        )

    async def update_member_profile(
        self,
        org_id: str,
        user_id: str,
        *,
        name: str | None = None,
        organization: str | None = None,
        job_title: str | None = None,
        bio: str | None = None,
        service_line: str | None = None,
        country: str | None = None,
        interest: str | None = None,
    ) -> OrganizationMemberRecord | None:
        """Edit the member's profile in this organization only (never the account)."""
        return await self.adapter.update_organization_member_profile(
            org_id=org_id,
            user_id=user_id,
            name=name,
            organization=organization,
            job_title=job_title,
            bio=bio,
            service_line=service_line,
            country=country,
            interest=interest,
        )

    async def set_member_avatar(self, org_id: str, user_id: str, avatar: str | None) -> str | None:
        """Set or clear the org avatar; returns the previous org avatar to clean up."""
        return await self.adapter.set_organization_member_avatar(
            org_id=org_id, user_id=user_id, avatar=avatar
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

    async def get_role_features(self, org_id: str) -> OrganizationRoleFeaturesRecord | None:
        return await self.adapter.get_organization_role_features(org_id=org_id)

    async def upsert_role_features(
        self,
        org_id: str,
        role_baseline: dict[str, list[str]],
        updated_by: str | None,
        now: datetime,
    ) -> OrganizationRoleFeaturesRecord:
        return await self.adapter.upsert_organization_role_features(
            org_id=org_id,
            role_baseline=role_baseline,
            updated_by=updated_by,
            now=now,
        )
