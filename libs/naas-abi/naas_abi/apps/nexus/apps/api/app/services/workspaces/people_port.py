"""The people service as the member routes consume it (epic #1566, S1's contract).

The platform's user directory (``services/people``, #1567) creates or links the
person an organization or a workspace invites, attaches what they were given on
behalf of the inviting person, and mails them. The member routes (workspaces,
organizations) and the agent's admin tools only call it through this port:

* ``PeopleServicePort`` and its types mirror the contract exactly;
* ``get_people_service`` is the route dependency, ``build_people_service`` what a
  caller with only a database session (the agent's tools) uses;
* ``people_http_error`` turns the service's domain errors into HTTP answers, by
  name, so the classes the service raises need not be these.

Wiring (the epic merge): set ``PEOPLE_SERVICE_FACTORY`` to what builds the
people service of ``services/people`` over a session, and re-export its types
here instead of the copies below.
"""

from __future__ import annotations

from collections.abc import Callable, Collection, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass
from enum import StrEnum
from typing import Any, Literal, Protocol

from fastapi import Depends, HTTPException
from naas_abi.apps.nexus.apps.api.app.core.database import get_db
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MembershipDenied
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession


class UserStatus(StrEnum):
    INVITED = "invited"
    ACTIVE = "active"


@dataclass(frozen=True)
class Grant:
    """One role or policy to attach."""

    scope: Literal["organization", "workspace"]
    scope_id: str  # org id or workspace id
    role: Literal["owner", "admin", "member", "viewer"] | None = None
    policy_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class PlatformUser:
    id: str  # = IAM principal id when bound; stable id while unbound
    email: str
    name: str | None
    status: UserStatus
    provider: str | None


@dataclass(frozen=True)
class CreateOrLinkResult:
    user: PlatformUser
    created: bool  # internal only: routes must NOT expose it
    provisioned: bool
    sign_in_email_sent: bool
    warning: str | None


class PeopleServicePort(Protocol):
    async def create_or_link(
        self,
        *,
        email: str,
        name: str | None,
        provider: str | None,
        grants: Sequence[Grant],
        by: Any,
        may_grant_owner: bool = False,
        profile: Mapping[str, str] | None = None,
        organization_id: str | None = None,
    ) -> CreateOrLinkResult: ...

    async def add_existing(
        self, *, user_id: str, grants: Sequence[Grant], by: Any, may_grant_owner: bool = False
    ) -> PlatformUser: ...

    async def get(self, user_id: str) -> PlatformUser | None: ...

    async def by_email(self, email: str) -> PlatformUser | None: ...

    async def search(
        self, *, q: str, among: Collection[str], limit: int = 10
    ) -> list[PlatformUser]: ...

    async def resend(self, *, user_id: str, by: Any) -> bool: ...

    async def activate(self, user_id: str) -> None: ...


class PeopleServiceUnavailableError(RuntimeError):
    """No people service is wired into this build (``build_people_service``)."""


# What makes the people service over a database session: ``services/people``'s
# (#1567), set here when the epic wires it. None: inviting answers 503.
PEOPLE_SERVICE_FACTORY: Callable[[AsyncSession], PeopleServicePort] | None = None


def people_service_wired() -> bool:
    """Whether this build has a people service (tests of the real flows need it)."""
    return PEOPLE_SERVICE_FACTORY is not None


def build_people_service(db: AsyncSession) -> PeopleServicePort:
    """The people service over ``db``."""
    if PEOPLE_SERVICE_FACTORY is None:
        raise PeopleServiceUnavailableError("The people service is not wired into this build")
    return PEOPLE_SERVICE_FACTORY(db)


# The tests that run the real create-or-link flows (provider, invitation, sign-in)
# through the member routes: they wait for the people service (#1567).
NEEDS_PEOPLE_SERVICE = (
    "The member invite routes create or link through the people service (#1566); "
    "this flow runs once it is wired (#1567), its assertions then follow the new answers"
)


def get_people_service(db: AsyncSession = Depends(get_db)) -> PeopleServicePort:
    try:
        return build_people_service(db)
    except PeopleServiceUnavailableError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


# The contract's domain errors and their HTTP answer, by class name (on the MRO).
_HTTP_STATUS_OF = {
    "GrantNotHeldError": 403,
    "OwnerGrantRefusedError": 403,
    "AlreadyMemberError": 409,
    "UnknownUserError": 404,
    "NoProviderError": 422,
    "ProvisioningFailedError": 502,
    # The identity provider's own failures, as the invitation routes answered them.
    "ProviderUnavailableError": 502,
    "ProvisioningError": 502,
    "ProvisioningRefused": 502,
    # What the request asked is not one (a role given as a policy, an unknown
    # workspace): the invite routes always answered these 400.
    "InvalidPolicyError": 400,
    "ValueError": 400,
}
_DEFAULT_DETAIL = {
    400: "Invalid request",
    403: "You cannot grant that role",
    404: "User not found",
    409: "Already a member",
    422: "No identity provider can take this person",
    502: "The identity provider could not create the user",
}


_OWNER_REFUSED = "Only owners can grant, change or remove an owner"


def people_http_error(exc: BaseException) -> HTTPException | None:
    """The HTTP answer to a people service error, None for any other exception.
    An unknown user is "not found" whatever the service said (it may name them)."""
    for cls in type(exc).__mro__:
        status = _HTTP_STATUS_OF.get(cls.__name__)
        if status is None:
            continue
        detail = str(exc) or _DEFAULT_DETAIL[status]
        if cls.__name__ == "OwnerGrantRefusedError":
            detail = _OWNER_REFUSED
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
        "provider": user.provider,
        "sign_in_email_sent": result.sign_in_email_sent,
        "warning": result.warning,
    }


def people_status(status: Any) -> str:
    """A status as the API spells it (``invited``, ``active``)."""
    return str(getattr(status, "value", status))


def status_of_row(row: Any) -> str:
    """A users row's status: its ``status`` column (#1567), else ``activated_at``
    when that is the column, else ``active`` (a row from before either)."""
    status = getattr(row, "status", None)
    if status:
        return people_status(status)
    if hasattr(row, "activated_at"):
        return (UserStatus.ACTIVE if row.activated_at is not None else UserStatus.INVITED).value
    return UserStatus.ACTIVE.value


MAX_CANDIDATES = 20
MIN_QUERY = 2
