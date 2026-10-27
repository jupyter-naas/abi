"""Grant only what you hold, in process: the shared scenarios
(``tests/grant_contract.py``) and who the giver is."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.adapters import iam_nats_codec as codec
from naas_abi_core.services.iam.IAMPorts import GrantNotHeldError, IIAMService
from naas_abi_core.services.iam.tests import grant_contract as contract
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness, statement

WS1, ORG_SCOPE, ORG_WIDE = contract.WS1, contract.ORG_SCOPE, contract.ORG_WIDE


def _as_user(h: IAMHarness):
    @contextmanager
    def as_user(record, scope=None) -> Iterator[IIAMService]:
        with h.as_(record, scope=scope):
            yield h.iam

    return as_user


@pytest.mark.parametrize("scenario", contract.SCENARIOS, ids=lambda s: s.__name__)
def test_grant_scenarios_in_process(h, scenario):
    scenario(h.iam, _as_user(h))


def test_api_acting_for_a_user_grants_what_the_user_holds_only(h):
    """``api`` holds the kernel services for its users: its statements never
    stand in for the user's."""
    t = contract.team(h.iam)
    with as_service_account("engine"):
        attacher = h.iam.ensure_user("https://idp.example", "attacher")
        policy = h.iam.create_policy(
            "attacher",
            contract.document(
                statement(
                    "Allow",
                    ["iam:AttachPolicy"],
                    ["${scope}:iam:attachment/builtin.viewer/*"],
                )
            ),
        )
        h.iam.attach_policy(policy.id, attacher.id, WS1)
    with (
        h.as_(actor="api", on_behalf_of=attacher),
        pytest.raises(GrantNotHeldError) as refused,
    ):
        h.iam.attach_policy(roles.VIEWER, t.colleague.id, WS1)
    assert "you do not hold it there" in str(refused.value)
    with h.as_(actor="api", on_behalf_of=t.admin):
        h.iam.attach_policy(roles.VIEWER, t.colleague.id, WS1)


def test_a_module_acting_for_a_user_is_bounded_by_both(h):
    t = contract.team(h.iam)
    account = h.service_account("module/acme/people")
    h.grant(
        account.id,
        statement("Allow", ["iam:AttachPolicy"], ["abi:*:*:iam:attachment/*"]),
    )
    with (
        h.as_(account, on_behalf_of=t.admin),
        pytest.raises(GrantNotHeldError) as refused,
    ):
        h.iam.attach_policy(roles.VIEWER, t.colleague.id, WS1)
    assert "module/acme/people, acting for you" in str(refused.value)


def test_first_party_writes_for_no_user_stay_allowed(h):
    """The org-wide mirror, seeding and the owner of what was just made are
    ``api``'s for no user; boot and feature policies the engine's."""
    t = contract.team(h.iam)
    with as_service_account("api"):
        h.iam.attach_policy(roles.OWNER, t.member.id, ORG_WIDE)
        h.iam.attach_policy(roles.PLATFORM_ADMIN, t.colleague.id)
    with as_service_account("engine"):
        h.iam.attach_policy(roles.OWNER, t.member.id, WS1)
        h.iam.put_feature_policies({"member": ["chat"]})


def test_an_existing_attachment_is_not_granted_again(h):
    t = contract.team(h.iam)
    with as_service_account("engine"):
        h.iam.attach_policy(roles.OWNER, t.colleague.id, WS1)
    with h.as_(t.owner):
        # Held already: attaching it again changes nothing, so nothing to hold.
        h.iam.attach_policy(roles.OWNER, t.colleague.id, WS1)


def test_existing_grants_are_not_checked_again(h):
    """The Decision: a granter losing a permission takes back nothing given."""
    t = contract.team(h.iam)
    with h.as_(t.admin):
        h.iam.attach_policy(roles.ADMIN, t.colleague.id, WS1)
    with as_service_account("engine"):
        h.iam.detach_policy(roles.ADMIN, t.admin.id, WS1)
    assert h.allowed(
        "triple_store:DropGraph", "abi:org-1:ws-1:triple_store:graph/g", t.colleague
    )


def test_the_refusal_travels_with_its_own_code():
    error = GrantNotHeldError(
        "triple_store:Insert",
        "abi:o:w:triple_store:graph/*",
        policy_id="pol_x",
        statement=0,
        sid="Write",
        scope="abi:o:w",
        reason="you do not hold it there",
    )
    assert codec.error_code(error) == "GRANT_NOT_HELD"
    assert str(error) == (
        "You cannot grant what you do not hold: statement 0 (Write) of pol_x allows "
        "triple_store:Insert on abi:o:w:triple_store:graph/* at abi:o:w, and you "
        "do not hold it there"
    )

    class Wire:
        code = "GRANT_NOT_HELD"
        message = str(error)

    with pytest.raises(GrantNotHeldError) as raised:
        codec.raise_for(Wire())
    assert str(raised.value) == str(error)


def test_grantable_needs_no_permission(h):
    stranger = h.user("stranger")
    with h.as_(stranger):
        assert contract._actions(h.iam.grantable(WS1)) == {}
        with pytest.raises(ValueError):
            h.iam.grantable("not a scope")
