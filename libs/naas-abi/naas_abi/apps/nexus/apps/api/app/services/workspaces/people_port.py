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
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import MembershipDenied
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
    NoProviderError,
    OwnerGrantRefusedError,
    PlatformUser,
    ProviderInfo,
    ProvisioningFailedError,
    ProvisioningRefused,
    RetiredIdentityError,
    UnknownUserError,
    UserStatus,
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
    "PeopleServicePort",
    "PlatformUser",
    "UserStatus",
    "added_result",
    "build_people_service",
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
        grants: Sequence[Grant],
        by: Any,
        may_grant_owner: bool = False,
        profile: Mapping[str, str] | None = None,
        organization_id: str | None = None,
    ) -> CreateOrLinkResult: ...

    async def add_existing(
        self, *, user_id: str, grants: Sequence[Grant], by: Any, may_grant_owner: bool = False
    ) -> AddedUser: ...

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
    (OwnerGrantRefusedError, 403),
    # What the request asked is not one (a malformed email or grant, an unknown
    # workspace): the invite routes always answered these 400.
    (ValueError, 400),
)
_DEFAULT_DETAIL = {
    400: "Invalid request",
    403: "You cannot grant that role",
    404: "User not found",
    409: "Already a member",
    422: "No identity provider can take this person",
    502: "The identity provider could not create the user",
}
_EMAIL_TAKEN = "This email belongs to another account"
_SIGNED_IN = "This member has already signed in"
_OWNER_REFUSED = "Only owners can grant, change or remove an owner"


def people_http_error(exc: BaseException) -> HTTPException | None:
    """The HTTP answer to a people service error, None for any other exception.
    An unknown user is "not found" whatever the service said (it may name them)."""
    for cls, status in _HTTP_STATUS_OF:
        if not isinstance(exc, cls):
            continue
        detail = str(exc) or _DEFAULT_DETAIL[status]
        if isinstance(exc, OwnerGrantRefusedError):
            detail = _OWNER_REFUSED
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
