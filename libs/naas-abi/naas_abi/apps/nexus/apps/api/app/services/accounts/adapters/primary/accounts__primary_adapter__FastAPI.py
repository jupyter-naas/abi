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
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__dependencies import (  # noqa: E501
    get_current_user_required,
)
from naas_abi.apps.nexus.apps.api.app.services.auth.adapters.primary.auth__primary_adapter__schemas import (  # noqa: E501
    User,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.guards import guard
from naas_abi.apps.nexus.apps.api.app.services.invites.port import (
    InvalidPolicyError,
    NoProviderError,
)
from naas_abi.apps.nexus.apps.api.app.services.sysadmin.resources import AuditUnavailable
from pydantic import BaseModel, Field

router = APIRouter()

LIST = "-"


class AdminUserOrganization(BaseModel):
    id: str
    name: str
    role: str


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


class AdminUserUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    is_superadmin: bool | None = None


class AdminUserInvite(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    name: str | None = Field(default=None, max_length=200)
    provider: str | None = None


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
    except DeletionBlocked as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except AccountExistsError as exc:
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
    current_user: User = Depends(get_current_user_required),
    service: AccountService = Depends(get_account_service),
) -> list[AdminUser]:
    """Every account, and everyone invited who has none yet."""
    return [admin_user(a) for a in await _answer(service.list(actor=current_user.id))]


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
    """Invite someone to the platform, through Nexus's invitations: their provider
    makes the account, and they get no role (attach their access once they have one)."""
    email = body.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(status_code=400, detail="Enter a valid email address")
    invited = await _answer(
        service.invite(
            actor=current_user.id,
            actor_name=current_user.name,
            email=email,
            name=(body.name or "").strip() or None,
            provider=body.provider or None,
        )
    )
    return AdminUserInvited(
        user=admin_user(invited.account),
        user_created=invited.user_created,
        sign_in_email_sent=invited.sign_in_email_sent,
        provisioning_skipped=invited.provisioning_skipped,
        renewed=invited.renewed,
        warning=invited.warning,
    )


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
    """Rename an account, and make it a platform admin or not."""
    if body.name is None and body.is_superadmin is None:
        raise HTTPException(status_code=400, detail="Nothing to change")
    account = None
    if body.name is not None:
        account = await _answer(service.rename(account_id, body.name, actor=current_user.id))
    if body.is_superadmin is not None:
        account = await _answer(
            service.set_superadmin(account_id, body.is_superadmin, actor=current_user.id)
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
