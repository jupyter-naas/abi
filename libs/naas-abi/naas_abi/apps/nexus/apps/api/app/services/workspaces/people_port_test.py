"""The people service as the member routes see it: one service (the people
runtime's), its own records, and each of its errors answered over HTTP, a subclass
as itself before its base."""

from __future__ import annotations

import pytest
from naas_abi.apps.nexus.apps.api.app.services.iam.memberships import UnknownUserError
from naas_abi.apps.nexus.apps.api.app.services.people import port as people
from naas_abi.apps.nexus.apps.api.app.services.people import runtime as people_runtime
from naas_abi.apps.nexus.apps.api.app.services.workspaces import people_port
from naas_abi.apps.nexus.apps.api.app.services.workspaces.people_testing import (
    FakePeopleService,
    installed,
)
from naas_abi_core.services.identity.IdentityPorts import (
    ProviderUnavailableError,
    ProvisioningError,
)


def test_the_routes_records_are_the_people_services_own() -> None:
    assert people_port.Grant is people.Grant
    assert people_port.PlatformUser is people.PlatformUser
    assert people_port.CreateOrLinkResult is people.CreateOrLinkResult
    assert people_port.UserStatus is people.UserStatus
    assert people_port.get_people_service is people_runtime.get_people_service


def test_the_routes_and_the_tools_get_the_service_installed() -> None:
    fake = FakePeopleService()
    with installed(fake):
        assert people_port.build_people_service(object()) is fake  # type: ignore[arg-type]
        assert people_runtime.get_people_service(object()) is fake  # type: ignore[arg-type]
    assert people_port.build_people_service(object()) is not fake  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("error", "status"),
    [
        (people.AlreadyActiveError("usr-1"), 409),
        (people.AlreadyMemberError("usr-1", "scope"), 409),
        (people.RetiredIdentityError("retired"), 409),
        (people.EmailTakenError("bob@example.com"), 409),
        (UnknownUserError("usr-1"), 404),
        (people.InvalidPolicyError("builtin.owner is a role"), 400),
        (people.NoProviderError("none"), 422),
        (people.ProvisioningFailedError("down"), 502),
        (people.ProvisioningRefused("no right"), 502),
        (ProviderUnavailableError("unreachable"), 502),
        (ProvisioningError("refused"), 502),
        (people.GrantNotHeldError("You cannot grant what you do not hold"), 403),
        (people.LastOrgAdminError("abi:nexus:organization/org-1"), 409),
        (ValueError("Enter a valid email address"), 400),
    ],
    ids=lambda v: type(v).__name__ if isinstance(v, BaseException) else str(v),
)
def test_each_error_of_the_service_is_its_http_answer(error: Exception, status: int) -> None:
    answer = people_port.people_http_error(error)
    assert answer is not None and answer.status_code == status


def test_the_answers_name_nobody_they_should_not() -> None:
    member = people_port.people_http_error(people.AlreadyMemberError("usr-1", "abi:nexus:x"))
    active = people_port.people_http_error(people.AlreadyActiveError("usr-1"))
    assert member is not None and member.detail == "Already a member"
    assert active is not None and active.detail == "This member has already signed in"
    unknown = people_port.people_http_error(UnknownUserError("usr-secret"))
    taken = people_port.people_http_error(people.EmailTakenError("bob@example.com"))
    last = people_port.people_http_error(people.LastOrgAdminError("abi:nexus:organization/x"))
    assert unknown is not None and unknown.detail == "User not found"
    assert taken is not None and "bob@example.com" not in str(taken.detail)
    assert last is not None and last.detail == "An organization keeps at least one admin"


def test_anything_else_is_not_the_people_services_to_answer() -> None:
    assert people_port.people_http_error(RuntimeError("boom")) is None
    assert people_port.people_http_error(KeyError("k")) is None


def test_the_provider_is_answered_as_the_invitation_routes_did() -> None:
    provider = people.ProviderInfo("corp", "Corp SSO", "https://corp.test", "none")
    assert people_port.provider_view(provider) == {
        "name": "corp",
        "display_name": "Corp SSO",
        "provisioning": "none",
        "managed_in_provider": True,
    }
    assert people_port.provider_view(None) is None


def test_a_workspace_body_maps_to_a_grant_and_the_role_of_before_too() -> None:
    grant = people_port.workspace_grant("org-1", "ws-1", level="viewer", capabilities=["grp_x"])
    assert grant == people.Grant(
        "org-1",
        level="viewer",
        workspaces=(people.WorkspaceAccess("ws-1"),),
        capabilities=("grp_x",),
    )
    assert people_port.level_and_admin(None, None, "admin") == (None, True)
    assert people_port.level_and_admin(None, None, "viewer") == ("viewer", False)
    assert people_port.level_and_admin("member", True, "viewer") == ("member", True)
    assert people_port.level_and_admin(None, None, None) == (None, False)
    for bad in ((None, None, "owner"), ("viewer", True, None), ("guest", None, None)):
        with pytest.raises(ValueError):
            people_port.level_and_admin(*bad)
