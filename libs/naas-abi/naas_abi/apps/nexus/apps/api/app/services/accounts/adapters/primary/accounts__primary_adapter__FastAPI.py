"""``/api/admin/users``: every account of the platform (Platform Settings > Users).

Each route declares its ``nexus`` action on the account (``abi:nexus:user/<id>``,
``-`` for the list and an invitation), which no role holds: the platform admin
does, or whoever a policy grants it. The change is then IAM's and the identity
provider's own, asked as the caller (``services/accounts``).
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.models import (
    OrganizationModel,
    UserModel,
    WorkspaceModel,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.port import (
    AccessRefused,
    Account,
    AccountChangeRefused,
    AccountExistsError,
    AccountNotFoundError,
    DeletionPlan,
    ProviderManaged,
    ProviderUnreachable,
)
from naas_abi.apps.nexus.apps.api.app.services.accounts.runtime import get_account_service
from naas_abi.apps.nexus.apps.api.app.services.accounts.service import (
    AccountService,
    DeletionBlocked,
    IdentityRetired,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    AccessSummary,
    MembershipDenied,
    UnknownUserError,
    is_user_principal_id,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import PLATFORM
from naas_abi.apps.nexus.apps.api.app.services.iam_admin.roles import (
    KEEP,
    ROLES_BATCH_MAX,
    HeldRolesView,
    MemberRolesInput,
    RoleChange,
    RoleOptionsView,
    RoleRefView,
    change_roles,
    held_roles,
    role_groups_of,
    role_options,
    roles_of_batch,
    roles_of_people,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    InvalidPolicyError,
    NoProviderError,
)
from naas_abi.apps.nexus.apps.api.app.services.invites.views import (
    PROVIDER_FAILURES,
    provider_failure,
)
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    EmailTakenError,
    ProvisioningFailedError,
    RetiredIdentityError,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()

LIST = "-"


class AdminUserOrganization(BaseModel):
    id: str
    name: str
    # Null: linked through one of the organization's workspaces only.
    role: str | None = None


class AdminUser(BaseModel):
    id: str
    kind: str = "account"
    email: str
    name: str
    avatar: str | None = None
    principal_id: str | None = None
    status: str = "signed_in"
    deactivated: bool = False
    is_superadmin: bool
    created_at: datetime | None = None
    organizations: list[AdminUserOrganization] = Field(default_factory=list)
    provider: str | None = None
    warning: str | None = None
    # Platform › Users › Role: their groups and policies at the platform.
    roles: list[RoleRefView] = Field(default_factory=list)


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    is_superadmin: bool | None = None


class AdminUserInvite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=200)
    provider: str | None = None
    # Make them a platform admin ("Platform admins"; #1589).
    platform_admin: bool = False


class AccessOrganization(BaseModel):
    id: str
    name: str
    org_admin: bool


class AccessWorkspace(BaseModel):
    id: str
    name: str
    organization_id: str | None
    admin: bool


class AccessCapability(BaseModel):
    id: str
    name: str
    owner_scope: str


class AdminUserAccess(BaseModel):
    """Where a person works and what they do (Platform › Users › person: "Platform
    access (automatic)"; #1589), read from their groups."""

    user_id: str
    principal_id: str
    level: str | None
    platform_admin: bool
    organizations: list[AccessOrganization]
    workspaces: list[AccessWorkspace]
    capabilities: list[AccessCapability]


class AdminUserInvited(BaseModel):
    user: AdminUser
    user_created: bool
    sign_in_email_sent: bool
    provisioning_skipped: bool
    renewed: bool
    warning: str | None = None


class DeletionProvider(BaseModel):
    provider: str
    display_name: str
    managed_in_provider: bool


class DeletionMembership(BaseModel):
    scope: str
    label: str
    role: str


class DeletionGoes(BaseModel):
    provider_account: DeletionProvider | None
    iam_user: str | None
    attachments: int
    memberships: list[DeletionMembership]
    groups: int
    sessions: int
    api_keys: int
    invitations: int


class DeletionWorkspace(BaseModel):
    id: str
    name: str


class DeletionStays(BaseModel):
    workspaces: list[DeletionWorkspace]


class AdminUserDeletion(BaseModel):
    user: AdminUser
    blocked: str | None
    # What deleting leaves behind (a provider that keeps the person's account).
    warning: str | None = None
    goes: DeletionGoes
    stays: DeletionStays


class AdminUserDeleted(BaseModel):
    deleted: bool = True
    warning: str | None = None


def admin_user(account: Account) -> AdminUser:
    return AdminUser(
        id=account.id,
        kind=account.kind,
        email=account.email,
        name=account.name,
        avatar=account.avatar,
        principal_id=account.principal_id,
        status=account.status,
        deactivated=account.deactivated,
        is_superadmin=account.is_superadmin,
        created_at=account.created_at,
        organizations=[
            AdminUserOrganization(id=o.id, name=o.name, role=o.role) for o in account.organizations
        ],
        provider=account.provider,
        warning=account.warning,
    )


def _deletion(plan: DeletionPlan) -> AdminUserDeletion:
    provider = plan.provider_account
    return AdminUserDeletion(
        user=admin_user(plan.account),
        blocked=plan.blocked,
        warning=plan.warning,
        goes=DeletionGoes(
            provider_account=DeletionProvider(
                provider=provider.name,
                display_name=provider.display_name,
                managed_in_provider=provider.managed_in_provider,
            )
            if provider is not None
            else None,
            iam_user=plan.iam_user,
            attachments=plan.attachments,
            memberships=[
                DeletionMembership(scope=m.scope, label=m.label, role=m.role)
                for m in plan.memberships
            ],
            groups=plan.groups,
            sessions=plan.sessions,
            api_keys=plan.api_keys,
            invitations=plan.invitations,
        ),
        stays=DeletionStays(
            workspaces=[DeletionWorkspace(id=i, name=n) for i, n in plan.workspaces]
        ),
    )


async def _answer(call: Any) -> Any:
    """The service's refusals as HTTP answers."""
    try:
        return await call
    except AccountNotFoundError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc
    except (DeletionBlocked, IdentityRetired) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (AccountExistsError, EmailTakenError, RetiredIdentityError) as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except (AccountChangeRefused, NoProviderError, InvalidPolicyError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except AccessRefused as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ProviderManaged as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except ProviderUnreachable as exc:
        raise HTTPException(
            status_code=502, detail=f"The identity provider could not do it: {exc}"
        ) from exc
    except ProvisioningFailedError as exc:
        raise HTTPException(
            status_code=502, detail=f"The identity provider could not create the user: {exc}"
        ) from exc
    except AuditUnavailable as exc:
        raise HTTPException(
            status_code=503, detail="The audit log is unavailable: nothing was changed"
        ) from exc


@router.get(
    "",
    response_model=list[AdminUser],
    dependencies=[guard("ListUsers", workspace=None, literal=LIST)],
)
async def list_users(
    roles: bool = Query(True, description="With each one's Role; false: the list alone."),
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> list[AdminUser]:
    """Every account, and everyone invited who has none yet, with their Role at the
    platform (``roles=false``: without it, read then a page at a time from
    ``GET /roles``)."""
    users = [admin_user(a) for a in await _answer(service.list(actor=current_user.id))]
    if not roles:
        return users
    found = await roles_of_people(PLATFORM, [u.principal_id for u in users if u.principal_id])
    for user in users:
        user.roles = found.get(str(user.principal_id), []) if user.principal_id else []
    return users


@router.get("/roles", dependencies=[guard("ListUsers", workspace=None, literal=LIST)])
async def users_roles(
    principal: list[str] = Query(default_factory=list, max_length=ROLES_BATCH_MAX),
) -> dict[str, list[RoleRefView]]:
    """Platform › Users › Role of the people asked by their IAM id (a page of them)."""
    return await roles_of_batch(PLATFORM, principal)


@router.post(
    "/invite",
    response_model=AdminUserInvited,
    dependencies=[guard("InviteUser", workspace=None, literal=LIST)],
)
async def invite_user(
    body: AdminUserInvite,
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> AdminUserInvited:
    """Invite someone to the platform: their account exists from now on, ``invited``
    until they sign in (``services/people``); their provider makes theirs. They get no
    access, unless ``platform_admin`` (checked as the caller once the account exists:
    a refusal leaves the account invited, without it)."""
    email = body.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    try:
        invited = await _answer(
            service.invite(
                actor=current_user.id,
                actor_name=current_user.name,
                email=email,
                name=(body.name or "").strip() or None,
                provider=body.provider or None,
            )
        )
    except PROVIDER_FAILURES as exc:
        # As the organization's and the workspace's invitations answer them.
        raise provider_failure(exc) from exc
    except ValueError as exc:  # an address the provider will not take
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    account = invited.account
    if body.platform_admin:
        account = await _answer(
            service.update(account.id, is_superadmin=True, actor=current_user.id)
        )
    return AdminUserInvited(
        user=admin_user(account),
        user_created=invited.user_created,
        sign_in_email_sent=invited.sign_in_email_sent,
        provisioning_skipped=invited.provisioning_skipped,
        renewed=invited.renewed,
        warning=invited.warning,
    )


async def _account_id(db: AsyncSession, person_id: str) -> str | None:
    """The account (an undeleted ``users`` row) of ``person_id``: its id, or its IAM id
    as the row records it once its person signed in through a provider."""
    found = await db.scalar(
        select(UserModel.id)
        .where(
            or_(UserModel.id == person_id, UserModel.principal_id == person_id),
            UserModel.deleted_at.is_(None),
        )
        .order_by(UserModel.id != person_id)
        .limit(1)
    )
    return str(found) if found is not None else None


async def _access_of_account(db: AsyncSession, person_id: str) -> AccessSummary | None:
    """What an account's groups give it, found by its id or its IAM id. IAM names the
    account of an IAM id the row does not record (linked from the old login); the
    account must still be one of the directory's. The session's reads run in turn."""
    account = await _account_id(db, person_id)
    if account is not None:
        return await MEMBERSHIPS.access_of(account)
    if not is_user_principal_id(person_id):
        return None  # an unknown account id: nothing is asked of IAM, nothing made there
    # IAM looks an IAM id up, and never creates it.
    summary = await MEMBERSHIPS.access_of(person_id)
    if summary is None or await _account_id(db, summary.user_id) != summary.user_id:
        return None
    return summary


@router.get(
    "/{account_id}/access",
    response_model=AdminUserAccess,
    dependencies=[guard("ListUsers", workspace=None, literal=LIST)],
)
async def user_access(account_id: str, db: AsyncSession = Depends(get_db)) -> AdminUserAccess:
    """Their level, the organizations they administer or belong to, their workspaces
    (and which they administer), their capability groups, and whether they are a
    platform admin: what their groups give them, nothing to edit here.

    ``account_id`` is their account's id or their IAM id (the person's page is opened by
    it, #1608): an account of the directory, never a deleted one, else 404."""
    summary = await _access_of_account(db, account_id)
    if summary is None:
        raise HTTPException(status_code=404, detail="User not found")
    org_ids = [o for o, _ in summary.organizations]
    ws_ids = [w for _, w, _ in summary.workspaces]
    orgs = {
        row.id: row.name
        for row in (
            await db.execute(select(OrganizationModel).where(OrganizationModel.id.in_(org_ids)))
        ).scalars()
    }
    workspaces = {
        row.id: row.name
        for row in (
            await db.execute(select(WorkspaceModel).where(WorkspaceModel.id.in_(ws_ids)))
        ).scalars()
    }
    return AdminUserAccess(
        user_id=summary.user_id,
        principal_id=summary.principal_id,
        level=summary.level,
        platform_admin=summary.platform_admin,
        organizations=[
            AccessOrganization(id=o, name=orgs.get(o, o), org_admin=admin)
            for o, admin in summary.organizations
        ],
        workspaces=[
            AccessWorkspace(id=w, name=workspaces.get(w, w), organization_id=o, admin=admin)
            for o, w, admin in summary.workspaces
        ],
        capabilities=[
            AccessCapability(id=g, name=name, owner_scope=owner)
            for g, name, owner in summary.capabilities
        ],
    )


@router.get(
    "/role-options",
    dependencies=[guard("ListUsers", workspace=None, literal=LIST)],
)
async def user_role_options(
    current_user: User = Depends(get_current_user_required),
) -> RoleOptionsView:
    """What a person's Role at the platform may hold, as the caller may give it: the
    levels, Platform admins, the platform's other groups the caller lists (Models ·
    all…), and the policies the caller may attach without a scope."""
    groups = await role_groups_of(PLATFORM)
    return await role_options(current_user, PLATFORM, groups, listed_at=None)


async def _person(account_id: str) -> tuple[str, str]:
    """``(their Nexus id, their IAM id)`` from either (a person's page names the IAM id)."""
    if is_user_principal_id(account_id):
        summary = await MEMBERSHIPS.access_of(account_id)
        if summary is None:
            raise HTTPException(status_code=404, detail="User not found")
        return summary.user_id, account_id
    try:
        return account_id, await MEMBERSHIPS.principal_id(account_id)
    except UnknownUserError as exc:
        raise HTTPException(status_code=404, detail="User not found") from exc


@router.get(
    "/{account_id}/roles",
    dependencies=[guard("ListUsers", workspace=None, literal=LIST)],
)
async def user_roles(account_id: str) -> HeldRolesView:
    """What a person holds at the platform (its groups, the policies attached to them
    without a scope), as a change of their Role starts from."""
    _user, principal = await _person(account_id)
    return await held_roles(PLATFORM, principal, await role_groups_of(PLATFORM))


@router.put(
    "/{account_id}/roles",
    dependencies=[guard("UpdateUser", workspace=None, id="account_id")],
)
async def set_user_roles(
    account_id: str,
    body: MemberRolesInput,
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> MemberRolesInput:
    """Make a person's Role at the platform the groups and policies asked: their level,
    whether they are a platform admin (the accounts' own rule: the platform keeps one),
    the platform's other groups and the policies attached without a scope, as the
    caller."""
    user_id, principal = await _person(account_id)
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot change your own access")
    groups = await role_groups_of(PLATFORM)

    async def seats(change: RoleChange, held: set[str]) -> set[str]:
        if change.admin is not None:
            await _answer(
                service.update(
                    user_id, name=None, is_superadmin=change.admin, actor=current_user.id
                )
            )
        if change.level not in (KEEP, None):
            try:
                await MEMBERSHIPS.set_level(user_id, str(change.level), by=current_user)
            except MembershipDenied as exc:
                raise HTTPException(status_code=403, detail=str(exc)) from exc
        return {groups.admins} if groups.admins else set()

    await change_roles(
        user=current_user,
        scope=PLATFORM,
        principal_id=principal,
        body=body,
        groups=groups,
        reaches_otherwise=True,
        attach_at=None,
        seats=seats,
    )
    return await held_roles(PLATFORM, principal, groups)


@router.patch(
    "/{account_id}",
    response_model=AdminUser,
    dependencies=[guard("UpdateUser", workspace=None, id="account_id")],
)
async def update_user(
    account_id: str,
    body: AdminUserUpdate,
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> AdminUser:
    """Rename an account, and make it a platform admin or not: both are checked
    before either is made, so a refused one leaves the other undone."""
    if body.name is None and body.is_superadmin is None:
        raise HTTPException(status_code=400, detail="Nothing to change")
    account = await _answer(
        service.update(
            account_id, name=body.name, is_superadmin=body.is_superadmin, actor=current_user.id
        )
    )
    return admin_user(account)


@router.post(
    "/{account_id}/deactivate",
    response_model=AdminUser,
    dependencies=[guard("SuspendUser", workspace=None, id="account_id")],
)
async def deactivate_user(
    account_id: str,
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> AdminUser:
    """No sign-in at the identity provider, no API call; data and memberships stay."""
    return admin_user(await _answer(service.deactivate(account_id, actor=current_user.id)))


@router.post(
    "/{account_id}/reactivate",
    response_model=AdminUser,
    dependencies=[guard("ResumeUser", workspace=None, id="account_id")],
)
async def reactivate_user(
    account_id: str,
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> AdminUser:
    return admin_user(await _answer(service.reactivate(account_id, actor=current_user.id)))


@router.get(
    "/{account_id}/deletion",
    response_model=AdminUserDeletion,
    dependencies=[guard("DeleteUser", workspace=None, id="account_id")],
)
async def user_deletion(
    account_id: str,
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> AdminUserDeletion:
    """What deleting the account takes away and what stays, and whether it may."""
    return _deletion(await _answer(service.deletion(account_id, actor=current_user.id)))


@router.delete(
    "/{account_id}",
    response_model=AdminUserDeleted,
    dependencies=[guard("DeleteUser", workspace=None, id="account_id")],
)
async def delete_user(
    account_id: str,
    confirm: str = Query("", description="The account's email, typed back"),
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> AdminUserDeleted:
    """Delete the account: at its identity provider, its IAM user with its
    attachments and memberships, its sessions and keys. What they wrote stays."""
    warning = await _answer(service.delete(account_id, confirm=confirm, actor=current_user.id))
    return AdminUserDeleted(warning=warning)
