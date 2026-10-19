"""Invitations and IdP group bindings (RFC §12.2).

``/api/invitations``

* ``GET    /providers``                      the providers an invitation can go
  through, and whether their people are made from ABI (``provisioning``) or
  managed in the provider (``none``: the UI says so).
* ``GET    /organizations/{org_id}``         pending invitations of an organization.
* ``GET    /workspaces/{workspace_id}``      pending invitations of a workspace.
* ``POST   /{invitation_id}/resend``         mail it again.
* ``DELETE /{invitation_id}``                withdraw it, and what it granted.

``/api/idp-groups``

* ``GET    /organizations/{org_id}`` and ``/workspaces/{workspace_id}``: the IdP
  groups bound to a role there, and the providers they can come from.
* ``PUT``  the same paths: ``{provider, group, role}`` binds one.
* ``DELETE`` the same paths with ``?provider=&group=&role=``: unbinds it.

Only owners and admins of the organization (or workspace) may. Inviting and
binding are Nexus's own calls to the engine, made once the route knows who asks.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.api.endpoints.auth import (
    User,
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.iam import authz
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import declares
from naas_abi.apps.nexus.apps.api.app.services.invites import runtime
from naas_abi.apps.nexus.apps.api.app.services.invites.names import (
    org_scope,
    workspace_scope,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    Invitation,
    InvitationNotFoundError,
    NoProviderError,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.service import InvitationService
from naas_abi.apps.nexus.apps.api.app.services.invites.views import (
    GroupBindingInput,
    GroupBindingsView,
    GroupBindingView,
    InvitationsView,
    ProvidersView,
    ProviderView,
    view,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.adapters.secondary.postgres import (
    OrganizationSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.organizations.service import OrganizationService
from naas_abi.apps.nexus.apps.api.app.services.workspaces.adapters.secondary.postgres import (
    WorkspaceSecondaryAdapterPostgres,
)
from naas_abi.apps.nexus.apps.api.app.services.workspaces.service import WorkspaceService
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, PermissionDeniedError
from naas_abi_core.services.identity.IdentityPorts import ProviderUnavailableError
from sqlalchemy.ext.asyncio import AsyncSession

invitations_router = APIRouter()
idp_groups_router = APIRouter()

get_invitations = runtime.get_invitation_service


def organizations(db: AsyncSession) -> OrganizationService:
    return OrganizationService(adapter=OrganizationSecondaryAdapterPostgres(db=db))


def workspaces(db: AsyncSession) -> WorkspaceService:
    return WorkspaceService(adapter=WorkspaceSecondaryAdapterPostgres(db=db))


async def require_org_admin(user: User, org_id: str, db: AsyncSession) -> None:
    """IAM decides (``InviteOrganizationMember`` is an admin's): whoever may invite
    to the organization may see, resend and withdraw its invitations and bind its groups."""
    del db
    await authz.require(
        "InviteOrganizationMember",
        user=user,
        org=org_id,
        id="-",
        denied="Only admins can manage invitations",
    )


async def require_workspace_admin(user: User, workspace_id: str, db: AsyncSession) -> None:
    del db
    await authz.require(
        "InviteWorkspaceMember",
        user=user,
        workspace=workspace_id,
        id="-",
        denied="Only admins can manage invitations",
    )


async def require_invitation_admin(user: User, invitation: Invitation, db: AsyncSession) -> None:
    """Whoever may invite where the invitation is may withdraw or resend it.

    An invitation that carries an organization role is the organization's
    administrators': withdrawing it drops that role's grant, which a workspace
    administrator could not make. One that names only a workspace is that
    workspace's administrators', and the organization's (who put people in any of
    its workspaces).
    """
    if invitation.org_role:
        if not invitation.organization_id:
            raise HTTPException(status_code=403, detail="Only admins can manage invitations")
        await require_org_admin(user, invitation.organization_id, db)
    elif invitation.workspace_id:
        try:
            await require_workspace_admin(user, invitation.workspace_id, db)
        except HTTPException:
            if not invitation.organization_id:
                raise
            await require_org_admin(user, invitation.organization_id, db)
    elif invitation.organization_id:
        await require_org_admin(user, invitation.organization_id, db)
    else:
        raise HTTPException(status_code=403, detail="Only admins can manage invitations")


async def names_of(invitation: Invitation, db: AsyncSession) -> tuple[str | None, str | None]:
    org_name = ws_name = None
    if invitation.organization_id:
        org = await organizations(db).get_organization(invitation.organization_id)
        org_name = org.name if org else None
    if invitation.workspace_id:
        ws = await workspaces(db).get_workspace(invitation.workspace_id)
        ws_name = ws.name if ws else None
    return org_name, ws_name


async def provider_views(invites: InvitationService) -> ProvidersView:
    try:
        known = await invites.providers()
    except ProviderUnavailableError:
        return ProvidersView(enabled=False)
    return ProvidersView(
        enabled=bool(known.providers),
        default_provider=known.default,
        providers=[
            ProviderView(
                name=p.name,
                display_name=p.display_name,
                provisioning=p.provisioning,
                managed_in_provider=p.managed_in_provider,
            )
            for p in known.providers
        ],
    )


# -- invitations -------------------------------------------------------------------------


@invitations_router.get("/providers")
async def list_invite_providers(
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
) -> ProvidersView:
    return await provider_views(invites)


@invitations_router.get(
    "/organizations/{org_id}", dependencies=[declares("InviteOrganizationMember")]
)
async def list_org_invitations(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> InvitationsView:
    await require_org_admin(current_user, org_id, db)
    found = await invites.pending(organization_id=org_id)
    return InvitationsView(invitations=[view(i) for i in found])


@invitations_router.get(
    "/workspaces/{workspace_id}", dependencies=[declares("InviteWorkspaceMember")]
)
async def list_workspace_invitations(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> InvitationsView:
    await require_workspace_admin(current_user, workspace_id, db)
    found = await invites.pending(workspace_id=workspace_id)
    return InvitationsView(invitations=[view(i) for i in found])


@invitations_router.post(
    "/{invitation_id}/resend",
    dependencies=[declares("InviteOrganizationMember"), declares("InviteWorkspaceMember")],
)
async def resend_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    invitation = await _pending(invites, invitation_id)
    await require_invitation_admin(current_user, invitation, db)
    org_name, ws_name = await names_of(invitation, db)
    try:
        sent = await invites.resend(
            invitation_id,
            inviter_name=current_user.name,
            organization_name=org_name,
            workspace_name=ws_name,
        )
    except NoProviderError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "pending", "sign_in_email_sent": sent}


@invitations_router.delete(
    "/{invitation_id}",
    dependencies=[declares("InviteOrganizationMember"), declares("InviteWorkspaceMember")],
)
async def revoke_invitation(
    invitation_id: str,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    invitation = await _pending(invites, invitation_id)
    await require_invitation_admin(current_user, invitation, db)
    await invites.revoke(invitation_id)
    return {"status": "revoked"}


async def _pending(invites: InvitationService, invitation_id: str) -> Invitation:
    try:
        invitation = await invites.get(invitation_id)
    except InvitationNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Invitation not found") from exc
    if invitation.status != "pending":
        raise HTTPException(status_code=404, detail="Invitation not found")
    return invitation


# -- IdP group bindings ------------------------------------------------------------------

ORG_ROLES = ["admin", "member"]
WORKSPACE_ROLES = ["admin", "member", "viewer"]


async def _bindings(invites: InvitationService, scope: str, roles: list[str]) -> GroupBindingsView:
    providers = await provider_views(invites)
    found = await invites.bindings([scope])
    return GroupBindingsView(
        providers=providers.providers,
        bindings=[
            GroupBindingView(provider=b.provider, group=b.claim_value, role=b.role) for b in found
        ],
        roles=roles,
    )


async def _change(
    invites: InvitationService,
    scope: str,
    roles: list[str],
    *,
    provider: str,
    group: str,
    role: str,
    unbind: bool,
) -> GroupBindingsView:
    """Bind or unbind, answering the same way for both: a role that cannot be
    bound here, a provider or group name that is refused, a right IAM withholds,
    or a binding that is not there are the caller's to read, never a 500."""
    if role not in roles:
        raise HTTPException(status_code=400, detail=f"role must be one of {', '.join(roles)}")
    try:
        if unbind:
            if not await invites.unbind_group(
                provider=provider, group=group, role=role, scope=scope
            ):
                raise HTTPException(status_code=404, detail="No such binding")
        else:
            await invites.bind_group(provider=provider, group=group, role=role, scope=scope)
    except (NoProviderError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except PermissionDeniedError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except IAMNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProviderUnavailableError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    return await _bindings(invites, scope, roles)


async def _bind(
    invites: InvitationService, body: GroupBindingInput, scope: str, roles: list[str]
) -> GroupBindingsView:
    return await _change(
        invites,
        scope,
        roles,
        provider=body.provider,
        group=body.group,
        role=body.role,
        unbind=False,
    )


@idp_groups_router.get(
    "/organizations/{org_id}", dependencies=[declares("InviteOrganizationMember")]
)
async def list_org_group_bindings(
    org_id: str,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> GroupBindingsView:
    await require_org_admin(current_user, org_id, db)
    return await _bindings(invites, org_scope(org_id), ORG_ROLES)


@idp_groups_router.put(
    "/organizations/{org_id}", dependencies=[declares("InviteOrganizationMember")]
)
async def bind_org_group(
    org_id: str,
    body: GroupBindingInput,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> GroupBindingsView:
    await require_org_admin(current_user, org_id, db)
    return await _bind(invites, body, org_scope(org_id), ORG_ROLES)


@idp_groups_router.delete(
    "/organizations/{org_id}", dependencies=[declares("InviteOrganizationMember")]
)
async def unbind_org_group(
    org_id: str,
    provider: str = Query(min_length=1, max_length=32),
    group: str = Query(min_length=1, max_length=256),
    role: str = Query(pattern=r"^(owner|admin|member|viewer)$"),
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> GroupBindingsView:
    await require_org_admin(current_user, org_id, db)
    return await _change(
        invites,
        org_scope(org_id),
        ORG_ROLES,
        provider=provider,
        group=group,
        role=role,
        unbind=True,
    )


async def _workspace_scope(workspace_id: str, db: AsyncSession) -> str:
    workspace = await workspaces(db).get_workspace(workspace_id)
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace_scope(workspace.organization_id, workspace_id)


@idp_groups_router.get(
    "/workspaces/{workspace_id}", dependencies=[declares("InviteWorkspaceMember")]
)
async def list_workspace_group_bindings(
    workspace_id: str,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> GroupBindingsView:
    await require_workspace_admin(current_user, workspace_id, db)
    scope = await _workspace_scope(workspace_id, db)
    return await _bindings(invites, scope, WORKSPACE_ROLES)


@idp_groups_router.put(
    "/workspaces/{workspace_id}", dependencies=[declares("InviteWorkspaceMember")]
)
async def bind_workspace_group(
    workspace_id: str,
    body: GroupBindingInput,
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> GroupBindingsView:
    await require_workspace_admin(current_user, workspace_id, db)
    scope = await _workspace_scope(workspace_id, db)
    return await _bind(invites, body, scope, WORKSPACE_ROLES)


@idp_groups_router.delete(
    "/workspaces/{workspace_id}", dependencies=[declares("InviteWorkspaceMember")]
)
async def unbind_workspace_group(
    workspace_id: str,
    provider: str = Query(min_length=1, max_length=32),
    group: str = Query(min_length=1, max_length=256),
    role: str = Query(pattern=r"^(owner|admin|member|viewer)$"),
    current_user: User = Depends(get_current_user_required),
    invites: InvitationService = Depends(get_invitations),
    db: AsyncSession = Depends(get_db),
) -> GroupBindingsView:
    await require_workspace_admin(current_user, workspace_id, db)
    scope = await _workspace_scope(workspace_id, db)
    return await _change(
        invites, scope, WORKSPACE_ROLES, provider=provider, group=group, role=role, unbind=True
    )
