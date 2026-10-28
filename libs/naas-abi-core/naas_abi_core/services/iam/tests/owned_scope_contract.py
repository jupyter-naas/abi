"""Policies and groups owned by an org or a workspace: the acceptance scenario,
run in process (``IAMService_owned_test.py``) and over NATS
(``IAMSecondaryAdapterNATSClient_test.py``).

``as_user(record)`` is a context manager yielding the ``IIAMService`` a call
makes as that user; the setup is the engine's, on ``iam`` directly.
"""

from __future__ import annotations

from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

import pytest
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    IIAMService,
    PermissionDeniedError,
    PrincipalRecord,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import document, graph, statement

ORG = "org-1"
WS1, WS2 = f"abi:{ORG}:ws-1", f"abi:{ORG}:ws-2"
ORG_SCOPE, ORG_WIDE = f"abi:{ORG}:-", f"abi:{ORG}:*"
OTHER_ORG = "abi:org-2:ws-9"
REFUSED = (IAMNotFoundError, PermissionDeniedError)

AsUser = Callable[[PrincipalRecord], AbstractContextManager[IIAMService]]


def reader(scope_var: str = "${scope}") -> dict:
    return document(
        statement(
            "Allow", ["triple_store:Query"], [f"{scope_var}:triple_store:graph/*"]
        )
    )


@dataclass
class Team:
    ws_admin: PrincipalRecord  # admin of ws-1
    org_admin: PrincipalRecord  # admin of the org, mirrored org-wide
    member: PrincipalRecord  # member of ws-1
    viewer: PrincipalRecord  # viewer of ws-1
    colleague: PrincipalRecord  # member of ws-2: in the org
    outsider: PrincipalRecord  # member of another org
    account: PrincipalRecord  # a service account
    ws2_policy: str
    ws2_group: str


def team(iam: IAMService) -> Team:
    with as_service_account("engine"):
        for org, ws in ((ORG, "ws-1"), (ORG, "ws-2"), ("org-2", "ws-9")):
            iam.put_scope(org)
            iam.put_scope(org, ws)
        users = {
            name: iam.ensure_user("https://idp.example", name)
            for name in (
                "ws-admin",
                "org-admin",
                "member",
                "viewer",
                "colleague",
                "outsider",
            )
        }
        iam.attach_policy(roles.ADMIN, users["ws-admin"].id, WS1)
        iam.attach_policy(roles.ADMIN, users["org-admin"].id, ORG_SCOPE)
        iam.attach_policy(roles.ADMIN, users["org-admin"].id, ORG_WIDE)
        iam.attach_policy(roles.MEMBER, users["member"].id, WS1)
        iam.attach_policy(roles.VIEWER, users["viewer"].id, WS1)
        iam.attach_policy(roles.MEMBER, users["colleague"].id, WS2)
        iam.attach_policy(roles.MEMBER, users["outsider"].id, OTHER_ORG)
        account = iam.create_service_account("ci/nightly")
        ws2_policy = iam.create_policy("ws-2 readers", reader(), scope=WS2)
        ws2_group = iam.create_group("ws-2 team", scope=WS2)
    return Team(
        users["ws-admin"],
        users["org-admin"],
        users["member"],
        users["viewer"],
        users["colleague"],
        users["outsider"],
        account,
        ws2_policy.id,
        ws2_group.id,
    )


def run_workspace_admin(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    with as_user(t.ws_admin) as admin:
        policy = admin.create_policy("ws-1 readers", reader(), scope=WS1)
        assert policy.owner_scope == WS1
        group = admin.create_group("ws-1 analysts", scope=WS1)
        assert (group.owner_scope, group.org) == (WS1, ORG)
        attachment = admin.attach_policy(policy.id, group.id, WS1)
        assert attachment.scope == WS1
        admin.add_group_member(group.id, t.member.id)
        admin.add_group_member(group.id, t.colleague.id)  # in the org, not in ws-1
        assert sorted(admin.list_group_members(group.id)) == sorted(
            [t.member.id, t.colleague.id]
        )
        updated = admin.update_policy(policy.id, expected_revision=1, name="readers")
        assert updated.name == "readers" and updated.owner_scope == WS1
        assert [
            p.id for p in admin.list_policies(scope=WS1).items if not p.managed
        ] == [policy.id]
        assert [g.id for g in admin.list_groups(scope=WS1).items] == [group.id]

        # Not ws-2's: neither read nor changed, nor named in a list.
        for call in (
            lambda: admin.get_policy(t.ws2_policy),
            lambda: admin.update_policy(t.ws2_policy, expected_revision=1, name="x"),
            lambda: admin.delete_policy(t.ws2_policy),
            lambda: admin.get_group(t.ws2_group),
            lambda: admin.add_group_member(t.ws2_group, t.member.id),
            lambda: admin.delete_group(t.ws2_group),
            lambda: admin.create_policy("mine", reader(), scope=WS2),
            lambda: admin.create_group("mine", scope=WS2),
        ):
            with pytest.raises(REFUSED):
                call()
        assert admin.list_policies(scope=WS2).items == []
        assert admin.list_groups(scope=WS2).items == []
        assert t.ws2_policy not in {p.id for p in admin.list_policies().items}
        assert t.ws2_group not in {g.id for g in admin.list_groups().items}
        # Nor the org's or the platform's own.
        with pytest.raises(REFUSED):
            admin.create_policy("org", reader(), scope=ORG_SCOPE)
        with pytest.raises(REFUSED):
            admin.create_policy("platform", reader())

        # A ws-1 policy goes at ws-1 only.
        with pytest.raises(REFUSED):
            admin.attach_policy(policy.id, t.member.id, WS2)
        # A user of another org, or a service account, never joins.
        with pytest.raises(ValueError):
            admin.add_group_member(group.id, t.outsider.id)
        with pytest.raises(ValueError):
            admin.add_group_member(group.id, t.account.id)
        # IdP group mappings stay the platform admin's.
        with pytest.raises(REFUSED):
            admin.map_idp_group("acme", "Sales", group.id)
    # The group's members read ws-1's graphs through it, nothing beyond.
    _assert_allowed(iam, t.colleague, "triple_store:Query", graph("g", ORG, "ws-1"))
    _assert_denied(iam, t.colleague, "triple_store:Query", graph("g", "org-2", "ws-9"))


def run_org_admin(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    with as_user(t.org_admin) as admin:
        assert admin.get_policy(t.ws2_policy).owner_scope == WS2
        admin.update_policy(t.ws2_policy, expected_revision=1, description="by the org")
        admin.add_group_member(t.ws2_group, t.colleague.id)
        admin.attach_policy(t.ws2_policy, t.ws2_group, WS2)
        org_policy = admin.create_policy("org readers", reader(), scope=ORG_SCOPE)
        org_group = admin.create_group("org analysts", scope=ORG_SCOPE)
        # An org's policy goes at the org, org-wide or at any of its workspaces.
        for scope in (ORG_SCOPE, ORG_WIDE, WS1, WS2):
            admin.attach_policy(org_policy.id, org_group.id, scope)
        # Never unscoped, never in another org.
        with pytest.raises(REFUSED):
            admin.attach_policy(org_policy.id, org_group.id, None)
        with pytest.raises(REFUSED):
            admin.attach_policy(org_policy.id, t.member.id, OTHER_ORG)
        # A ws-2 policy never at ws-1, a ws-2 group never receives at ws-1.
        with pytest.raises(ValueError):
            admin.attach_policy(t.ws2_policy, t.member.id, WS1)
        with pytest.raises(ValueError):
            admin.attach_policy(org_policy.id, t.ws2_group, WS1)
        assert {g.id for g in admin.list_groups(scope=WS2).items} == {
            t.ws2_group,
            org_group.id,
        }
        assert {p.id for p in admin.list_policies(scope=ORG_SCOPE).items} >= {
            org_policy.id
        }
        admin.delete_group(t.ws2_group)
        admin.detach_policy(org_policy.id, org_group.id, WS2)


def run_members_and_viewers(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    for who in (t.member, t.viewer):
        with as_user(who) as session:
            for call in (
                lambda: session.create_policy("x", reader(), scope=WS1),
                lambda: session.create_group("x", scope=WS1),
                lambda: session.get_policy(t.ws2_policy),
                lambda: session.get_group(t.ws2_group),
                lambda: session.attach_policy(roles.VIEWER, t.outsider.id, WS1),
                lambda who=who: session.detach_policy(roles.VIEWER, who.id, WS1),
            ):
                with pytest.raises(REFUSED):
                    call()
            assert session.list_policies(scope=WS1).items == []
            assert session.list_groups(scope=WS1).items == []
            assert session.list_policies().items == []
            assert session.list_groups().items == []
            assert session.list_attachments(principal_id=who.id) == []


def run_owned_documents(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    with as_user(t.ws_admin) as admin:
        # An owned policy names only ${scope}: resources, a Deny's included.
        for doc in (
            document(statement("Allow", ["triple_store:Query"], ["*"])),
            document(
                statement(
                    "Allow", ["triple_store:Query"], ["${scope}:triple_store:graph/*"]
                ),
                statement(
                    "Deny", ["triple_store:Query"], ["abi:*:*:triple_store:graph/*"]
                ),
            ),
        ):
            with pytest.raises(ValueError):  # PolicyValidationError in process
                admin.create_policy("wide", doc, scope=WS1)
        policy = admin.create_policy("ok", reader(), scope=WS1)
        with pytest.raises(ValueError):
            admin.update_policy(
                policy.id,
                expected_revision=1,
                document=document(statement("Allow", ["triple_store:Query"], ["*"])),
            )
        with pytest.raises(ValueError):
            admin.create_policy("org-wide", reader(), scope=ORG_WIDE)


def run_platform_denies_at_a_scope(iam: IAMService, as_user: AsUser) -> None:
    """A platform policy with a Deny beyond ${scope}: is attached at a scope by
    the platform admin only: a scope's admin or owner could otherwise impose
    the Deny on anyone, in any org, the platform admin included."""
    t = team(iam)
    with as_service_account("engine"):
        root = iam.ensure_user("https://idp.example", "root")
        iam.attach_policy(roles.PLATFORM_ADMIN, root.id)
        owner = iam.ensure_user("https://idp.example", "ws-owner")
        iam.attach_policy(roles.OWNER, owner.id, WS1)
    with as_user(root) as session:
        guard = session.create_policy(
            "guardrail",
            document(
                statement(
                    "Allow", ["triple_store:Query"], ["${scope}:triple_store:graph/*"]
                ),
                statement("Deny", ["iam:*", "triple_store:Insert"], ["*"]),
            ),
        )
        shared_reader = session.create_policy("shared reader", reader())
    for who in (t.ws_admin, owner):
        with as_user(who) as session:
            offered = {p.id for p in session.list_policies(scope=WS1).items}
            assert guard.id not in offered and shared_reader.id in offered
            for target in (t.outsider, root, t.member):
                with pytest.raises(REFUSED):
                    session.attach_policy(guard.id, target.id, WS1)
            with pytest.raises(REFUSED):
                session.create_pending_grant(
                    "builtin", "eve@example.com", guard.id, WS1
                )
            with pytest.raises(REFUSED):
                session.bind_idp_group("acme", "Sales", guard.id, WS1)
            # Wholly within ${scope}:, a platform policy is still theirs to attach.
            session.attach_policy(shared_reader.id, t.member.id, WS1)
    _assert_allowed(iam, root, "iam:CreatePolicy", "abi:%2A:%2A:iam:policy/x")
    _assert_allowed(
        iam, t.outsider, "triple_store:Insert", "abi:org-2:ws-9:triple_store:graph/g"
    )
    with as_user(root) as session:
        assert guard.id in {p.id for p in session.list_policies(scope=WS1).items}
        session.attach_policy(guard.id, t.member.id, WS1)
        session.create_pending_grant("builtin", "eve@example.com", guard.id, WS1)
        session.bind_idp_group("acme", "Sales", guard.id, WS1)


def _assert_allowed(
    iam: IAMService, user: PrincipalRecord, action: str, name: str
) -> None:
    from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

    assert IAMHarness(iam).allowed(action, name, user)


def _assert_denied(
    iam: IAMService, user: PrincipalRecord, action: str, name: str
) -> None:
    from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

    assert not IAMHarness(iam).allowed(action, name, user)


SCENARIOS = (
    run_workspace_admin,
    run_org_admin,
    run_members_and_viewers,
    run_owned_documents,
    run_platform_denies_at_a_scope,
)
