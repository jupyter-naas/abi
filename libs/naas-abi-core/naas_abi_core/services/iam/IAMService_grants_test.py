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
from naas_abi_core.services.iam.names import anywhere
from naas_abi_core.services.iam.tests import grant_contract as contract
from naas_abi_core.services.iam.tests.iam_harness import (
    IAMHarness,
    below,
    graph,
    statement,
    workspace,
)

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
                    ["${scope}/iam:attachment/builtin.viewer/*"],
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
        statement("Allow", ["iam:AttachPolicy"], anywhere("iam:attachment/*")),
    )
    with (
        h.as_(account, on_behalf_of=t.admin),
        pytest.raises(GrantNotHeldError) as refused,
    ):
        h.iam.attach_policy(roles.VIEWER, t.colleague.id, WS1)
    assert "module/acme/people, acting for you" in str(refused.value)


def test_an_actor_for_no_user_holds_no_user_variable(h):
    """``${user.id}`` names no one for an account acting for no user: what it
    names there is not the account's to grant."""
    t = contract.team(h.iam)
    account = h.service_account("ci/grants")
    h.grant(
        account.id,
        statement("Allow", ["iam:AttachPolicy"], anywhere("iam:attachment/*")),
        statement(
            "Allow",
            ["triple_store:Query"],
            [f"{WS1}/triple_store:graph/${{user.id}}/*"],
        ),
    )
    with as_service_account("engine"):
        mine = h.iam.create_policy(
            "mine",
            contract.reader(resources=["${scope}/triple_store:graph/${user.id}/*"]),
        )
    with h.as_(account), pytest.raises(GrantNotHeldError) as refused:
        h.iam.attach_policy(mine.id, t.member.id, WS1)
    assert "${user.id}" in str(refused.value)
    # Acting for a user, it binds to them: the account holds it for them.
    with h.as_(account, on_behalf_of=t.admin):
        h.iam.attach_policy(mine.id, t.member.id, WS1)


def test_first_party_writes_for_no_user_stay_allowed(h):
    """The org-wide mirror, seeding and the owner of what was just made are
    ``api``'s for no user; boot the engine's."""
    t = contract.team(h.iam)
    with as_service_account("api"):
        h.iam.attach_policy(roles.OWNER, t.member.id, ORG_WIDE)
        h.iam.attach_policy(roles.PLATFORM_ADMIN, t.colleague.id)
    with as_service_account("engine"):
        h.iam.attach_policy(roles.OWNER, t.member.id, WS1)


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
    assert h.allowed("triple_store:DropGraph", graph("g"), t.colleague)


def test_the_refusal_travels_with_its_own_code():
    where = workspace("w", "o")
    error = GrantNotHeldError(
        "triple_store:Insert",
        f"{where}/triple_store:graph/*",
        policy_id="pol_x",
        statement=0,
        sid="Write",
        scope=where,
        reason="you do not hold it there",
    )
    assert codec.error_code(error) == "GRANT_NOT_HELD"
    assert str(error) == (
        "You cannot grant what you do not hold: statement 0 (Write) of pol_x allows "
        f"triple_store:Insert on {where}/triple_store:graph/* at {where}, and you "
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


# -- where a policy is held (#1519) ------------------------------------------------

READ_ALL = statement("Allow", ["triple_store:Query"], ["${scope}/triple_store:graph/*"])
OFF = statement(
    "Deny", ["triple_store:Query"], ["${scope}/triple_store:graph/secret"], sid="Off"
)


def _turned_off(h: IAMHarness, where: str, who) -> None:
    """``who`` holds, at the workspace ``where``, its access: every graph but
    ``secret`` (a workspace's turned-off item, as the upgrade writes it)."""
    with as_service_account("engine"):
        access = h.iam.create_policy(
            "access", contract.document(READ_ALL, OFF), scope=where
        )
        h.iam.attach_policy(access.id, who.id, where)


def test_a_deny_in_another_organisation_does_not_stop_a_platform_policy(h):
    """The platform admin, denied ``secret`` in ws-1 of org-1, writes and widens
    org-2's access (a platform policy attached below org-2): it is held where it
    applies, the platform itself and below org-2, never in every container."""
    t = contract.team(h.iam)
    h.register("ws-3", "org-2")
    _turned_off(h, WS1, t.root)
    olivia = h.user("olivia")
    with h.as_(t.root):
        access = h.iam.create_policy("org-2 access", contract.document(READ_ALL))
        h.iam.attach_policy(access.id, olivia.id, below("org-2"))
        h.iam.update_policy(
            access.id,
            expected_revision=1,
            document=contract.document(
                statement(
                    "Allow",
                    ["triple_store:Query", "triple_store:Insert"],
                    ["${scope}/triple_store:graph/*"],
                )
            ),
        )
    assert h.allowed("triple_store:Query", graph("secret", "org-2", "ws-3"), olivia)
    assert h.allowed("triple_store:Insert", graph("secret", "org-2", "ws-3"), olivia)
    # ws-1 still denies it to whoever holds its access, the platform admin included.
    assert not h.allowed("triple_store:Query", graph("secret"), t.root)
    assert h.allowed("triple_store:Query", graph("open"), t.root)
    assert not h.allowed("triple_store:Query", graph("secret"), olivia)


def test_a_deny_where_the_policy_applies_still_stops_it(h):
    """Denied ``secret`` in ws-3 of org-2, the platform admin may not give it
    below org-2, where the policy is attached."""
    t = contract.team(h.iam)
    ws3 = h.register("ws-3", "org-2")
    _turned_off(h, ws3, t.root)
    olivia = h.user("olivia")
    with h.as_(t.root):
        access = h.iam.create_policy(
            "org-2 access",
            contract.document(
                statement(
                    "Allow", ["triple_store:Query"], ["${scope}/triple_store:graph/x"]
                )
            ),
        )
        h.iam.attach_policy(access.id, olivia.id, below("org-2"))
        contract.refused(
            lambda: h.iam.update_policy(
                access.id, expected_revision=1, document=contract.document(READ_ALL)
            ),
            graph("secret", "org-2", "ws-3"),
            f"at {below('org-2')}",
        )
        contract.refused(
            lambda: h.iam.attach_policy(
                h.iam.create_policy("wide", contract.document(READ_ALL)).id,
                olivia.id,
                below("org-2"),
            ),
            graph("secret", "org-2", "ws-3"),
        )
    assert not h.allowed("triple_store:Query", graph("y", "org-2", "ws-3"), olivia)


def test_an_organisation_admin_still_gives_only_what_it_holds_where_it_applies(h):
    """Denied ``secret`` in ws-1, the org's admin writes an org policy of every
    graph (held at the org itself), and may not attach it below the org."""
    t = contract.team(h.iam)
    _turned_off(h, WS1, t.org_admin)
    with h.as_(t.org_admin):
        wide = h.iam.create_policy("wide", contract.document(READ_ALL), scope=ORG_SCOPE)
        contract.refused(
            lambda: h.iam.attach_policy(wide.id, t.colleague.id, ORG_WIDE),
            graph("secret"),
        )
