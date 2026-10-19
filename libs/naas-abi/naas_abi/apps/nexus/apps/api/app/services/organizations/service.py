from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import uuid4

from naas_abi.apps.nexus.apps.api.app.services.iam.authz import AUTHZ, Authz
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    ROLE_NAMES,
    Memberships,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    nexus_resource,
    org_scope,
    workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.port import (
    OrganizationCreateInput,
    OrganizationDomainCreateInput,
    OrganizationDomainRecord,
    OrganizationMemberRecord,
    OrganizationPermissionPort,
    OrganizationRecord,
    OrganizationRoleFeaturesRecord,
    OrganizationUpdateInput,
    OrganizationWorkspaceMembershipRecord,
    OrganizationWorkspaceRecord,
)
from naas_abi_core import logger


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


def _member_id(org_id: str, user_id: str) -> str:
    return f"member-{org_id}-{user_id}"


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
    scope (``abi:<org>:-``), and org membership never grants a workspace.
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
        return await self.memberships.role_at(user_id, org_scope(org_id))

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
            resource_of=lambda row: nexus_resource("organization", org=row.id),
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
            resource_of=lambda row: nexus_resource("workspace", org=org_id, workspace=row.id),
        )

    async def list_all_workspaces(self, org_id: str) -> list[OrganizationWorkspaceRecord]:
        return await self.adapter.list_workspaces_for_org(org_id=org_id)

    async def list_workspace_memberships(
        self, org_id: str
    ) -> list[OrganizationWorkspaceMembershipRecord]:
        found: list[OrganizationWorkspaceMembershipRecord] = []
        for workspace in await self.adapter.list_workspaces_for_org(org_id=org_id):
            members = await self.memberships.members(workspace_scope(org_id, workspace.id))
            found += [
                OrganizationWorkspaceMembershipRecord(
                    user_id=member.user_id, workspace_id=workspace.id, role=member.role
                )
                for member in members
            ]
        return found

    async def list_members(self, org_id: str) -> list[OrganizationMemberRecord]:
        members = await self.memberships.members(org_scope(org_id))
        users = await self.adapter.get_users_by_ids([m.user_id for m in members])
        return [
            OrganizationMemberRecord(
                id=_member_id(org_id, member.user_id),
                organization_id=org_id,
                user_id=member.user_id,
                role=member.role,
                email=users[member.user_id].email,
                name=users[member.user_id].name,
                created_at=member.since,
            )
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
        """Give an existing user by email a role. Callers that support
        create-on-invite must ensure the user exists (via
        AuthService.ensure_user_for_invite) first. ``MembershipDenied`` when IAM
        refuses ``by`` this role (granting ``owner`` is the owner's)."""
        normalized_email = email.lower().strip()
        user = await self.adapter.get_user_by_email(email=normalized_email)
        if user is None:
            return None
        scope = org_scope(org_id)
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
        scope = org_scope(org_id)
        held = await self.memberships.role_at(user_id, scope)
        if held is None:
            return None
        if held == "owner" and role != "owner":
            await self.memberships.check(user_id, role, scope, by=by)
            await self._keep_an_owner(scope, user_id)
        await self.memberships.grant(user_id, role, scope, by=by)
        return await self.get_organization_member(org_id, user_id)

    async def remove_member(self, org_id: str, user_id: str, *, by: Any) -> bool:
        """Drop the member's role; the owners are removed by changing their role first."""
        scope = org_scope(org_id)
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
