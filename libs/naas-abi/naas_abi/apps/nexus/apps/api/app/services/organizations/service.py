from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, Authz
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    ROLE_NAMES,
    Member,
    Memberships,
    best,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_container,
    workspace_container,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationMemberDetailsRecord,
    OrganizationMemberProfileRecord,
    OrganizationMemberRecord,
    OrganizationPermissionPort,
    OrganizationRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceMembershipRecord,
    OrganizationWorkspaceRecord,
    UserOrganizationMembershipRecord,
    UserRecord,
)
from naas_abi_core import logger


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
    inherited_role: str | None,
    workspaces: list[OrganizationWorkspaceRecord],
    memberships: list[OrganizationWorkspaceMembershipRecord],
) -> list[MemberWorkspaceAccess]:
    """The member's effective role on each workspace of the org: the highest of the
    role they hold in it, ownership of it, and the organization-wide role their
    org role carries (``inherited_role``: an org owner or admin)."""
    explicit = {m.workspace_id: m.role for m in memberships if m.user_id == user_id}
    access: list[MemberWorkspaceAccess] = []
    for workspace in workspaces:
        own = best(
            [
                r
                for r in (
                    explicit.get(workspace.id),
                    "owner" if workspace.owner_id == user_id else None,
                )
                if r
            ]
        )
        role = best([r for r in (own, inherited_role) if r])
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
class LastOwnerError(ValueError):
    """The change would leave the organization without an owner."""

    scope: str

    def __str__(self) -> str:
        return "last_owner"


def new_org_id() -> str:
    return f"org-{uuid4().hex[:12]}"


def _member_id(org_id: str, user_id: str) -> str:
    return f"member-{org_id}-{user_id}"


def _member_record(
    org_id: str,
    member: Member,
    user: UserRecord,
    profile: OrganizationMemberProfileRecord | None,
) -> OrganizationMemberRecord:
    """A member as the organization shows them: the full name is always the
    account's; the picture, organization, job title and the rest are what the
    organization set (the account falls back to them, never the other way round);
    the bio falls back to the account's."""
    profile = profile or OrganizationMemberProfileRecord()
    return OrganizationMemberRecord(
        id=_member_id(org_id, member.user_id),
        organization_id=org_id,
        user_id=member.user_id,
        role=member.role,
        email=user.email,
        name=user.name,
        created_at=member.since,
        bio=profile.bio if profile.bio is not None else user.bio,
        avatar=profile.avatar,
        organization=profile.organization,
        job_title=profile.job_title,
        service_line=profile.service_line,
        country=profile.country,
        interest=profile.interest,
    )


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
    """Organizations and their members.

    Membership is IAM's: a member holds ``builtin.<role>`` at the organization's
    container (``abi:nexus:organization/<org>``), and org membership never grants a
    workspace (owners and admins also hold theirs below it, which reaches each).
    ``by`` names the signed-in user making a change, whose own rights IAM checks
    (an admin can never grant, demote or remove an owner).
    """

    def __init__(
        self,
        adapter: OrganizationPermissionPort,
        memberships: Memberships = MEMBERSHIPS,
        authz: Authz | None = None,
    ):
        self.adapter = adapter
        self.memberships = memberships
        self._authz = authz or AUTHZ

    async def get_organization_role(self, user_id: str, org_id: str) -> str | None:
        return await self.memberships.role_at(user_id, org_container(org_id))

    async def require_organization_access(self, user_id: str, org_id: str) -> str:
        role = await self.get_organization_role(user_id=user_id, org_id=org_id)
        if role is None:
            raise OrganizationPermissionError(org_id=org_id, user_id=user_id)
        return role

    async def list_organizations(self, user_id: str) -> list[OrganizationRecord]:
        """The organizations IAM lets the user list (``nexus:ListOrganizations``)."""
        rows = await self.adapter.list_all_organizations()
        return await self._authz.filter(
            "ListOrganizations",
            rows,
            user=user_id,
            resource_of=lambda row: org_container(row.id),
        )

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
        org_id: str | None = None,
    ) -> OrganizationRecord:
        """``org_id``: decided by the caller that checked the create on the new
        organization's own name (``new_org_id``); made here when None."""
        if await self.adapter.organization_slug_exists(slug=slug):
            raise OrganizationSlugAlreadyExistsError(slug=slug)

        org_id = org_id or new_org_id()
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
        # The row exists before IAM knows it, and memberships live only in IAM:
        # an organization nobody owns could not be administered or deleted, so a
        # failure undoes what was done (the compensation of create_workspace).
        try:
            scope = await self.memberships.register_org(record.id)
            await self.memberships.grant(owner_id, "owner", scope)
        except Exception:
            await self._undo_create(record.id)
            raise
        return record

    async def _undo_create(self, org_id: str) -> None:
        for undo in (
            lambda: self.memberships.drop_scope(org_id, None),
            lambda: self.adapter.delete_organization(org_id=org_id),
        ):
            try:
                await undo()
            except Exception:  # noqa: BLE001 - the original failure is what is raised
                logger.exception(f"Could not undo the creation of organization {org_id}")

    async def update_organization(
        self,
        org_id: str,
        updates: OrganizationUpdateInput,
    ) -> OrganizationRecord | None:
        return await self.adapter.update_organization(org_id=org_id, updates=updates)

    async def list_workspaces(self, org_id: str, user_id: str) -> list[OrganizationWorkspaceRecord]:
        """The org's workspaces the user may list (``nexus:ListWorkspaces``)."""
        rows = await self.adapter.list_workspaces_for_org(org_id=org_id)
        return await self._authz.filter(
            "ListWorkspaces",
            rows,
            user=user_id,
            resource_of=lambda row: nexus_resource(
                "workspace", container=workspace_container(org_id, row.id)
            ),
        )

    async def list_all_workspaces(self, org_id: str) -> list[OrganizationWorkspaceRecord]:
        return await self.adapter.list_workspaces_for_org(org_id=org_id)

    async def list_workspace_memberships(
        self, org_id: str
    ) -> list[OrganizationWorkspaceMembershipRecord]:
        found: list[OrganizationWorkspaceMembershipRecord] = []
        for workspace in await self.adapter.list_workspaces_for_org(org_id=org_id):
            members = await self.memberships.members(workspace_container(org_id, workspace.id))
            found += [
                OrganizationWorkspaceMembershipRecord(
                    user_id=member.user_id, workspace_id=workspace.id, role=member.role
                )
                for member in members
            ]
        return found

    async def list_all_memberships(self) -> list[UserOrganizationMembershipRecord]:
        """Every user's organizations across the platform (Platform Settings), from IAM."""
        found = [
            UserOrganizationMembershipRecord(
                user_id=member.user_id,
                organization_id=org.id,
                organization_name=org.name,
                role=member.role,
            )
            for org in await self.adapter.list_all_organizations()
            for member in await self.memberships.members(org_container(org.id))
        ]
        return sorted(found, key=lambda m: (m.user_id, m.organization_name))

    async def list_members(self, org_id: str) -> list[OrganizationMemberRecord]:
        members = await self.memberships.members(org_container(org_id))
        users = await self.adapter.get_users_by_ids([m.user_id for m in members])
        profiles = await self.adapter.list_organization_member_profiles(org_id)
        return [
            _member_record(org_id, member, users[member.user_id], profiles.get(member.user_id))
            for member in members
            if member.user_id in users
        ]

    async def get_organization_member(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberRecord | None:
        return next((m for m in await self.list_members(org_id) if m.user_id == user_id), None)

    async def invite_member(
        self,
        org_id: str,
        email: str,
        role: str,
        now: datetime,
        *,
        by: Any,
    ) -> OrganizationMemberRecord | None:
        """Give an existing user by email a role. Someone with no account is
        invited through an identity provider instead (``services/invites``).
        ``MembershipDenied`` when IAM
        refuses ``by`` this role (granting ``owner`` is the owner's)."""
        normalized_email = email.lower().strip()
        user = await self.adapter.get_user_by_email(email=normalized_email)
        if user is None:
            return None
        scope = org_container(org_id)
        if await self.memberships.role_at(user.id, scope) is not None:
            raise OrganizationMemberAlreadyExistsError(org_id=org_id, user_id=user.id)
        await self.memberships.grant(user.id, role, scope, by=by)
        return OrganizationMemberRecord(
            id=_member_id(org_id, user.id),
            organization_id=org_id,
            user_id=user.id,
            role=role,
            email=user.email,
            name=user.name,
            created_at=now,
        )

    async def update_member_role(
        self,
        org_id: str,
        user_id: str,
        role: str,
        *,
        by: Any,
    ) -> OrganizationMemberRecord | None:
        if role not in ROLE_NAMES:
            return None
        scope = org_container(org_id)
        held = await self.memberships.role_at(user_id, scope)
        if held is None:
            return None
        if held == "owner" and role != "owner":
            await self.memberships.check(user_id, role, scope, by=by)
            await self._keep_an_owner(scope, user_id)
        await self.memberships.grant(user_id, role, scope, by=by)
        return await self.get_organization_member(org_id, user_id)

    async def get_member_details(
        self, org_id: str, user_id: str
    ) -> OrganizationMemberDetailsRecord | None:
        member = await self.get_organization_member(org_id, user_id)
        account = await self.adapter.get_member_account(user_id)
        if member is None or account is None:
            return None
        profile = await self.adapter.get_organization_member_profile(org_id, user_id)
        return OrganizationMemberDetailsRecord(
            member=member,
            account=account,
            organization_profile=profile or OrganizationMemberProfileRecord(),
        )

    async def get_member_workspace_access(
        self, org_id: str, user_id: str
    ) -> list[MemberWorkspaceAccess]:
        return member_workspace_access(
            user_id=user_id,
            inherited_role=await self.memberships.inherited_role(user_id, org_id),
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
        if await self.memberships.role_at(user_id, org_container(org_id)) is None:
            return None
        await self.adapter.update_organization_member_profile(
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
        return await self.get_organization_member(org_id, user_id)

    async def set_member_avatar(self, org_id: str, user_id: str, avatar: str | None) -> str | None:
        """Set or clear the org avatar; returns the previous org avatar to clean up."""
        if await self.memberships.role_at(user_id, org_container(org_id)) is None:
            return None
        return await self.adapter.set_organization_member_avatar(
            org_id=org_id, user_id=user_id, avatar=avatar
        )

    async def remove_member(self, org_id: str, user_id: str, *, by: Any) -> bool:
        """Drop the member's role; the owners are removed by changing their role first."""
        scope = org_container(org_id)
        held = await self.memberships.role_at(user_id, scope)
        if held is None or held == "owner":
            return False
        return await self.memberships.revoke(user_id, scope, by=by)

    async def _keep_an_owner(self, scope: str, leaving: str) -> None:
        owners = [m for m in await self.memberships.members(scope) if m.role == "owner"]
        if all(m.user_id == leaving for m in owners):
            raise LastOwnerError(scope)

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

    async def set_domain_provider(
        self, org_id: str, domain_id: str, provider: str | None
    ) -> OrganizationDomainRecord | None:
        """Route the domain's logins to a configured identity provider; the
        caller checked that ``provider`` is one."""
        return await self.adapter.set_organization_domain_provider(
            org_id=org_id, domain_id=domain_id, provider=provider
        )
