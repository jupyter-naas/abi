"""Policies and groups owned by an org or a workspace, in process: the shared
scenario (``tests/owned_scope_contract.py``) and what only the service shows."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import IAMNotFoundError, IIAMService
from naas_abi_core.services.iam.IAMService import (
    group_resource,
    policy_resource,
)
from naas_abi_core.services.iam.policy import PolicyValidationError
from naas_abi_core.services.iam.tests import owned_scope_contract as contract
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

WS1, WS2, ORG_SCOPE = contract.WS1, contract.WS2, contract.ORG_SCOPE


def _as_user(h: IAMHarness):
    @contextmanager
    def as_user(record) -> Iterator[IIAMService]:
        with h.as_(record):
            yield h.iam

    return as_user


@pytest.mark.parametrize("scenario", contract.SCENARIOS, ids=lambda s: s.__name__)
def test_owned_scenarios_in_process(h, scenario):
    scenario(h.iam, _as_user(h))


def test_names_carry_the_owner():
    assert policy_resource("pol_x", WS1) == "abi:org-1:ws-1:iam:policy/pol_x"
    assert group_resource("grp_x", ORG_SCOPE) == "abi:org-1:-:iam:group/grp_x"
    # The platform's are named for every org: no ${scope} reaches them.
    assert policy_resource("pol_x") == "abi:%2A:%2A:iam:policy/pol_x"
    assert group_resource("grp_x") == "abi:%2A:%2A:iam:group/grp_x"


def test_members_and_viewers_hold_nothing_of_iam():
    from naas_abi_core.services.iam.catalog import CatalogRegistry
    from naas_abi_core.services.iam.iam_catalog import CATALOG

    registry = CatalogRegistry()
    registry.register(CATALOG)
    for role in (roles.VIEWER, roles.MEMBER):
        statements = roles.role_policy(role, registry).document.statements
        assert not any(a.startswith("iam:") for s in statements for a in s.actions)
    for role in (roles.ADMIN, roles.OWNER):
        actions = {
            a
            for s in roles.role_policy(role, registry).document.statements
            for a in s.actions
        }
        assert {"iam:CreatePolicy", "iam:AddGroupMember", "iam:ListGroups"} <= actions
        assert not actions & {"iam:MapIdpGroup", "iam:UnmapIdpGroup"}


def test_an_owner_scope_must_be_registered(h):
    root = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    with h.as_(root):
        with pytest.raises(ValueError):
            h.iam.create_policy("x", contract.reader(), scope="abi:org-x:ws-x")
        with pytest.raises(ValueError):
            h.iam.create_group("x", org="org-x")
        with pytest.raises(ValueError):
            h.iam.create_group("x", org="org-1", scope="abi:org-2:-")


def test_an_owned_policy_refuses_what_reaches_beyond_its_scope(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin), pytest.raises(PolicyValidationError) as refused:
        h.iam.create_policy(
            "wide",
            contract.document(contract.statement("Deny", ["*"], ["*"])),
            scope=WS1,
        )
    assert "'*'" in str(refused.value)


def test_a_workspace_admin_sees_what_it_may_attach_from_above(h):
    t = contract.team(h.iam)
    with as_service_account("engine"):
        org_policy = h.iam.create_policy(
            "org readers", contract.reader(), scope=ORG_SCOPE
        )
        platform_policy = h.iam.create_policy("platform readers", contract.reader())
        org_group = h.iam.create_group("org analysts", scope=ORG_SCOPE)
        platform_group = h.iam.create_group("platform analysts")
    with h.as_(t.ws_admin):
        listed = {p.id for p in h.iam.list_policies(scope=WS1).items}
        assert {org_policy.id, platform_policy.id, roles.ADMIN, roles.VIEWER} <= listed
        assert roles.OWNER not in listed  # an admin never attaches owner
        assert t.ws2_policy not in listed
        # Attached from above at ws-1, to a group of the org.
        h.iam.attach_policy(org_policy.id, org_group.id, WS1)
        groups = {g.id for g in h.iam.list_groups(scope=WS1).items}
        assert org_group.id in groups and platform_group.id not in groups
        # Not read one by one: only listed where they may be attached.
        with pytest.raises(IAMNotFoundError):
            h.iam.get_policy(org_policy.id)


def test_a_user_who_leaves_the_org_leaves_its_groups(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin):
        group = h.iam.create_group("analysts", scope=WS1)
        h.iam.add_group_member(group.id, t.member.id)
        h.iam.detach_policy(roles.MEMBER, t.member.id, WS1)
    with as_service_account("engine"):
        assert h.iam.list_group_members(group.id) == []


def test_deleting_a_workspace_deletes_what_it_owns(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin):
        policy = h.iam.create_policy("readers", contract.reader(), scope=WS1)
        group = h.iam.create_group("analysts", scope=WS1)
        h.iam.attach_policy(policy.id, group.id, WS1)
        h.iam.attach_policy(policy.id, t.member.id, WS1)
        h.iam.create_pending_grant("builtin", "eve@example.com", policy.id, WS1)
    with as_service_account("engine"):
        org_policy = h.iam.create_policy("org", contract.reader(), scope=ORG_SCOPE)
        h.iam.delete_scope("org-1", "ws-1")
        with pytest.raises(IAMNotFoundError):
            h.iam.get_policy(policy.id)
        assert h.iam.get_group(group.id).status == "deleted"
        assert h.iam.list_attachments(policy_id=policy.id) == []
        assert h.iam.list_pending_grants(policy_id=policy.id) == []
        # What ws-2 and the org own stays, until the org goes.
        assert h.iam.get_policy(t.ws2_policy).owner_scope == WS2
        assert h.iam.get_policy(org_policy.id).owner_scope == ORG_SCOPE
        h.iam.delete_scope("org-1")
        for policy_id in (t.ws2_policy, org_policy.id):
            with pytest.raises(IAMNotFoundError):
                h.iam.get_policy(policy_id)
        assert h.iam.get_group(t.ws2_group).status == "deleted"


def test_deleting_a_workspace_takes_its_members_out_of_the_orgs_groups(h):
    """Bob is in the org through ws-1 only: when ws-1 goes, he leaves the
    org's groups and what they grant at ws-2, though a policy of the org was
    still attached to him at ws-1 (nothing but IAM detaches that)."""
    t = contract.team(h.iam)
    ws2_graph = f"{WS2}:triple_store:graph/g"
    with h.as_(t.org_admin):
        readers = h.iam.create_policy("readers", contract.reader(), scope=ORG_SCOPE)
        group = h.iam.create_group("analysts", scope=ORG_SCOPE)
        h.iam.attach_policy(readers.id, group.id, WS2)
        h.iam.add_group_member(group.id, t.member.id)
        h.iam.add_group_member(group.id, t.colleague.id)
        h.iam.attach_policy(readers.id, t.member.id, WS1)
    with h.as_(t.member):
        assert h.iam.authorize("triple_store:Query", ws2_graph).allowed
    with as_service_account("engine"):
        h.iam.delete_scope("org-1", "ws-1")
        assert h.iam.list_group_members(group.id) == [t.colleague.id]
        assert not any(
            a.scope == WS1 for a in h.iam.list_attachments(principal_id=t.member.id)
        )
    with h.as_(t.member):
        assert not h.iam.authorize("triple_store:Query", ws2_graph).allowed


def test_a_binding_group_belongs_to_the_org_of_its_scope(h):
    contract.team(h.iam)
    with as_service_account("engine"):
        first = h.iam.bind_idp_group("acme", "Sales", roles.VIEWER, WS1)
        again = h.iam.bind_idp_group("acme", "Sales", roles.VIEWER, WS2)
        other = h.iam.bind_idp_group("acme", "Sales", roles.VIEWER, contract.OTHER_ORG)
        assert first.group_id == again.group_id != other.group_id
        assert h.iam.get_group(first.group_id).owner_scope == ORG_SCOPE
        assert h.iam.get_group(other.group_id).owner_scope == "abi:org-2:-"


def test_platform_groups_keep_their_rules(h):
    t = contract.team(h.iam)
    with as_service_account("engine"):
        group = h.iam.create_group("everyone")
        h.iam.add_group_member(group.id, t.account.id)
        h.iam.add_group_member(group.id, t.outsider.id)
        h.iam.attach_policy(roles.VIEWER, group.id, WS1)
        h.iam.attach_policy(roles.VIEWER, group.id, contract.OTHER_ORG)


def test_a_group_of_another_workspace_is_not_found_when_attaching(h):
    t = contract.team(h.iam)
    with h.as_(t.ws_admin):
        policy = h.iam.create_policy("readers", contract.reader(), scope=WS1)
        with pytest.raises(IAMNotFoundError):
            h.iam.attach_policy(policy.id, t.ws2_group, WS1)
        with pytest.raises(IAMNotFoundError):
            h.iam.attach_policy(t.ws2_policy, t.member.id, WS1)
