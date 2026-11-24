"""The people service as the member routes consume it (epic #1566).

The platform's user directory (``services/people``, #1567) creates or links the
person an organization or a workspace invites, attaches what they were given on
behalf of the inviting person, and mails them. The member routes (workspaces,
organizations) and the agent's admin tools only call it through this module:

* the records (``Grant``, ``PlatformUser``…) are ``services/people``'s own,
  re-exported here; ``PeopleServicePort`` is what the routes call of it;
* ``get_people_service`` is the route dependency and ``build_people_service`` what a
  caller with only a database session (the agent's tools) uses: both are the
  people runtime's (``services/people/runtime.py``), so a test installs another
  service for all of them with ``people.runtime.configure`` (``people_testing``);
* ``people_http_error`` turns the service's domain errors into HTTP answers.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from typing import Any, Protocol

from fastapi import HTTPException
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import (
    MEMBERSHIPS,
    MembershipDenied,
)
from naas_abi.apps.nexus.apps.api.app.services.iam.names import PLATFORM
from naas_abi.apps.nexus.apps.api.app.services.people import runtime as people_runtime
from naas_abi.apps.nexus.apps.api.app.services.people.port import (
    MAX_SEARCH,
    MIN_QUERY,
    AddedUser,
    AlreadyActiveError,
    AlreadyMemberError,
    CreateOrLinkResult,
    EmailTakenError,
    Grant,
    GrantNotHeldError,
    InvalidPolicyError,
    LastOrgAdminError,
    Level,
    NoProviderError,
    PlatformUser,
    ProviderInfo,
    ProvisioningFailedError,
    ProvisioningRefused,
    RetiredIdentityError,
    UnknownUserError,
    UserStatus,
    WorkspaceAccess,
    people_status,
    status_of_row,
)
from naas_abi.apps.nexus.apps.api.app.services.people.runtime import get_people_service
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisioningError,
)
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

__all__ = [
    "MAX_CANDIDATES",
    "MIN_QUERY",
    "AddedUser",
    "CreateOrLinkResult",
    "Grant",
    "LAST_ORG_ADMIN",
    "Level",
    "PeopleServicePort",
    "PlatformUser",
    "UserStatus",
    "WorkspaceAccess",
    "added_result",
    "build_people_service",
    "capability_group_items",
    "level_and_admin",
    "workspace_grant",
    "get_people_service",
    "people_errors",
    "people_http_error",
    "people_status",
    "provider_view",
    "status_of_row",
]

MAX_CANDIDATES = MAX_SEARCH


class PeopleServicePort(Protocol):
    """What the routes and the agent's tools call of ``PeopleService``."""

    async def create_or_link(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        grant: Grant | None,
        by: Any,
        profile: Mapping[str, str] | None = None,
        organization_id: str | None = None,
    ) -> CreateOrLinkResult: ...

    async def add_existing(self, *, user_id: str, grant: Grant, by: Any) -> AddedUser: ...

    async def set_level(
        self, *, user_id: str, level: str, by: Any, where: Sequence[str] = ()
    ) -> Level | None: ...

    async def set_workspace_admin(
        self, *, user_id: str, workspace_id: str, admin: bool, by: Any
    ) -> None: ...

    async def change_access(
        self,
        *,
        user_id: str,
        organization_id: str,
        by: Any,
        level: str | None = None,
        org_admin: bool | None = None,
        workspaces: Sequence[WorkspaceAccess] | None = None,
        among: Sequence[str] = (),
        capabilities: Sequence[str] | None = None,
    ) -> None: ...

    async def get(self, user_id: str) -> PlatformUser | None: ...

    async def by_email(self, email: str) -> PlatformUser | None: ...

    async def search(
        self, *, q: str, among: Collection[str], limit: int = 10
    ) -> list[PlatformUser]: ...

    async def resend(self, *, user_id: str, by: Any) -> bool: ...

    async def activate(self, user_id: str) -> None: ...


def build_people_service(db: AsyncSession) -> PeopleServicePort:
    """The people service over ``db`` (the runtime installed: ``configure``)."""
    return people_runtime.RUNTIME.service(db)


# The service's domain errors and their HTTP answer. Checked in this order, so a
# subclass is answered as itself before its base: ``AlreadyActiveError`` is an
# ``AlreadyMemberError``, and ``RetiredIdentityError``, ``UnknownUserError`` and
# ``InvalidPolicyError`` are ``ValueError``s, which are a 400 only when nothing
# more specific matched.
_HTTP_STATUS_OF: tuple[tuple[type[BaseException], int], ...] = (
    (AlreadyMemberError, 409),  # AlreadyActiveError too: a resend to someone signed in
    (LastOrgAdminError, 409),
    (RetiredIdentityError, 409),
    (EmailTakenError, 409),
    (UnknownUserError, 404),
    (InvalidPolicyError, 400),
    (NoProviderError, 422),
    (ProvisioningFailedError, 502),
    # The identity provider's own failures, as the invitation routes answered them.
    (ProvisioningRefused, 502),
    (ProviderUnavailableError, 502),
    (ProvisioningError, 502),
    (GrantNotHeldError, 403),
    # What the request asked is not one (a malformed email or grant, an unknown
    # workspace): the invite routes always answered these 400.
    (ValueError, 400),
)
_DEFAULT_DETAIL = {
    400: "Invalid request",
    403: "You cannot give this access",
    404: "User not found",
    409: "Already a member",
    422: "No identity provider can take this person",
    502: "The identity provider could not create the user",
}
_EMAIL_TAKEN = "This email belongs to another account"
_SIGNED_IN = "This member has already signed in"
LAST_ORG_ADMIN = "An organization keeps at least one admin"


def people_http_error(exc: BaseException) -> HTTPException | None:
    """The HTTP answer to a people service error, None for any other exception.
    An unknown user is "not found" whatever the service said (it may name them)."""
    for cls, status in _HTTP_STATUS_OF:
        if not isinstance(exc, cls):
            continue
        detail = str(exc) or _DEFAULT_DETAIL[status]
        if isinstance(exc, LastOrgAdminError):
            detail = LAST_ORG_ADMIN
        elif isinstance(exc, AlreadyActiveError):
            detail = _SIGNED_IN
        elif isinstance(exc, AlreadyMemberError):
            # Not the container names IAM keeps: who and where the caller knows.
            detail = _DEFAULT_DETAIL[409]
        elif isinstance(exc, EmailTakenError):
            detail = _EMAIL_TAKEN
        elif status == 404:
            detail = _DEFAULT_DETAIL[404]
        elif status == 502:
            detail = f"{_DEFAULT_DETAIL[502]}: {exc}" if str(exc) else _DEFAULT_DETAIL[502]
        return HTTPException(status_code=status, detail=detail)
    return None


@contextmanager
def people_errors(denied: Callable[[str], HTTPException]) -> Iterator[None]:
    """Answer the people service's refusals over HTTP (``people_http_error``); a
    role IAM refused the caller is ``denied(role)``."""
    try:
        yield
    except HTTPException:
        raise
    except MembershipDenied as exc:
        raise denied(str(exc)) from exc
    except Exception as exc:
        answer = people_http_error(exc)
        if answer is None:
            raise
        raise answer from exc


def level_and_admin(
    level: str | None, admin: bool | None, role: str | None
) -> tuple[Level | None, bool]:
    """``(level, admin)`` a request asks for at a workspace: ``level`` and ``admin``,
    else the role of before (#1589): ``admin`` an admin, ``member`` or ``viewer`` that
    level. Owner is not assigned any more; a Viewer administers nothing
    (``ValueError``: 400)."""
    if level is None and admin is None and role is not None:
        if role == "owner":
            raise ValueError("Owner is no longer assigned: make them an admin")
        if role == "admin":
            return None, True
        level = role
    if level is not None and level not in ("viewer", "member"):
        raise ValueError(f"Unknown level {level!r}")
    if level == "viewer" and admin:
        raise ValueError("A workspace admin is a Member: a Viewer administers nothing")
    return level, bool(admin)  # type: ignore[return-value]


def workspace_grant(
    organization_id: str | None,
    workspace_id: str,
    *,
    level: str | None = None,
    admin: bool | None = None,
    role: str | None = None,
    capabilities: Sequence[str] = (),
) -> Grant:
    """The grant of a workspace's add or invite: the person joins it (``level`` and
    ``admin``, or the role of before, ``level_and_admin``) and the capability groups."""
    chosen, is_admin = level_and_admin(level, admin, role)
    return Grant(
        organization_id,
        level=chosen,
        workspaces=(WorkspaceAccess(workspace_id, is_admin),),
        capabilities=tuple(capabilities),
    )


async def capability_group_items(organization_id: str | None) -> list[dict[str, object]]:
    """The capability groups a person may be put in, in ``organization_id`` (None: a
    workspace in no organization): the organization's own, then the platform's. The
    model's own groups (levels, memberships, admins) are not listed."""
    groups = await MEMBERSHIPS.capability_groups(organization_id)
    return [
        {
            "id": str(g.id),
            "name": str(g.name),
            "description": getattr(g, "description", None) or None,
            "owner_scope": str(g.owner_scope),
            "scope": "platform" if g.owner_scope == PLATFORM else "organization",
        }
        for g in groups
    ]


def provider_view(provider: ProviderInfo | None) -> dict[str, object] | None:
    """A provider as the invitation routes always answered it (``ProviderView``)."""
    if provider is None:
        return None
    return {
        "name": provider.name,
        "display_name": provider.display_name,
        "provisioning": provider.provisioning,
        "managed_in_provider": provider.managed_in_provider,
    }


def added_result(result: CreateOrLinkResult, member: BaseModel | None) -> dict[str, object]:
    """What the invite routes answer, the same whether the account was created or
    linked: nothing tells one from the other (``created`` stays internal)."""
    user = result.user
    return {
        "status": "added",
        "user": {
            "id": user.id,
            "email": user.email,
            "name": user.name,
            "status": people_status(user.status),
        },
        "member": member.model_dump(mode="json") if member is not None else None,
        "provider": provider_view(result.provider),
        "sign_in_email_sent": result.sign_in_email_sent,
        "warning": result.warning,
    }
