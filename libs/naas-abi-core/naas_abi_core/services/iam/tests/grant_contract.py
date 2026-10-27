"""Grant only what you hold: the acceptance scenarios, run in process
(``IAMService_grants_test.py``) and over NATS
(``IAMSecondaryAdapterNATSClient_test.py``).

``as_user(record, scope=None)`` is a context manager yielding the
``IIAMService`` a call makes as that user, narrowed by ``scope`` (a token's
``abi_scope``) when given; the setup is the engine's, on ``iam`` directly.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
from dataclasses import dataclass
from typing import Any

import pytest
from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    as_service_account,
    use_call_context,
)
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    GrantNotHeldError,
    IIAMService,
    PrincipalRecord,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import document, statement

ORG = "org-1"
WS1, WS2 = f"abi:{ORG}:ws-1", f"abi:{ORG}:ws-2"
ORG_SCOPE, ORG_WIDE = f"abi:{ORG}:-", f"abi:{ORG}:*"
QUERY, INSERT = "triple_store:Query", "triple_store:Insert"
GRAPHS = "${scope}:triple_store:graph/*"

# Nexus's feature type, as Nexus registers it: no role reaches it.
NEXUS = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(ResourceType("feature", id="opaque"),),
    actions=(ActionSpec("UseFeature", "read", ("feature",)),),
)

AsUser = Callable[..., AbstractContextManager[IIAMService]]


def reader(actions: Sequence[str] = (QUERY,), resources: Sequence[str] = (GRAPHS,)):
    return document(statement("Allow", list(actions), list(resources)))


@dataclass
class Team:
    owner: PrincipalRecord  # owner of ws-1
    admin: PrincipalRecord  # admin of ws-1
    org_admin: PrincipalRecord  # admin of the org, mirrored org-wide
    member: PrincipalRecord  # member of ws-1
    colleague: PrincipalRecord  # member of ws-2
    root: PrincipalRecord  # the platform admin


def team(iam: IAMService) -> Team:
    with as_service_account("engine"):
        for ws in ("ws-1", "ws-2"):
            iam.put_scope(ORG)
            iam.put_scope(ORG, ws)
        users = {
            name: iam.ensure_user("https://idp.example", name)
            for name in ("owner", "admin", "org-admin", "member", "colleague", "root")
        }
        iam.attach_policy(roles.OWNER, users["owner"].id, WS1)
        iam.attach_policy(roles.ADMIN, users["admin"].id, WS1)
        iam.attach_policy(roles.ADMIN, users["org-admin"].id, ORG_SCOPE)
        iam.attach_policy(roles.ADMIN, users["org-admin"].id, ORG_WIDE)
        iam.attach_policy(roles.MEMBER, users["member"].id, WS1)
        iam.attach_policy(roles.MEMBER, users["colleague"].id, WS2)
        iam.attach_policy(roles.PLATFORM_ADMIN, users["root"].id)
    return Team(
        users["owner"],
        users["admin"],
        users["org-admin"],
        users["member"],
        users["colleague"],
        users["root"],
    )


def custom(iam: IAMService, name: str, *statements: dict, scope: str | None = WS1):
    """A user holding one custom policy, attached at ``scope`` with a viewer's
    role there (unscoped: alone)."""
    with as_service_account("engine"):
        user = iam.ensure_user("https://idp.example", name)
        policy = iam.create_policy(name, document(*statements))
        iam.attach_policy(policy.id, user.id, scope)
        if scope is not None:
            iam.attach_policy(roles.VIEWER, user.id, scope)
    return user


def refused(call: Callable[[], Any], *named: str) -> GrantNotHeldError:
    with pytest.raises(GrantNotHeldError) as found:
        call()
    for part in named:
        assert part in str(found.value), str(found.value)
    return found.value


def run_narrower_admin_writes_wider_policy(iam: IAMService, as_user: AsUser) -> None:
    team(iam)
    editor = custom(
        iam,
        "editor",
        statement(
            "Allow",
            ["iam:CreatePolicy", "iam:UpdatePolicy", "iam:GetPolicy"],
            ["${scope}:iam:policy/*"],
        ),
        statement("Allow", [QUERY], [GRAPHS]),
    )
    with as_user(editor) as session:
        policy = session.create_policy("readers", reader(), scope=WS1)
        refused(
            lambda: session.create_policy("writers", reader([INSERT]), scope=WS1),
            INSERT,
            "abi:org-1:ws-1:triple_store:graph/*",
        )
        # A wildcard expands to what the catalog has: Insert among it.
        refused(
            lambda: session.create_policy("all", reader(["triple_store:*"]), scope=WS1),
            "triple_store:",
        )
        refused(
            lambda: session.update_policy(
                policy.id, expected_revision=1, document=reader([QUERY, INSERT])
            ),
            INSERT,
            policy.id,
        )
        # A Deny needs no cover.
        session.update_policy(
            policy.id,
            expected_revision=1,
            document=document(
                statement("Allow", [QUERY], [GRAPHS]),
                statement(
                    "Deny", ["triple_store:*"], ["${scope}:triple_store:graph/hr*"]
                ),
            ),
        )


def run_admin_cannot_make_itself_owner(iam: IAMService, as_user: AsUser) -> None:
    """The escalation #373 opened: a policy that attaches owner, made and
    attached by an admin of the workspace or of the org."""
    t = team(iam)
    escalate = document(
        statement(
            "Allow",
            ["iam:AttachPolicy"],
            ["${scope}:iam:attachment/builtin.owner/*"],
        )
    )
    for who, scope in ((t.admin, WS1), (t.org_admin, ORG_SCOPE)):
        with as_user(who) as session, pytest.raises(GrantNotHeldError) as found:
            session.create_policy("esc", escalate, scope=scope)
        assert "attachment/builtin.owner/*" in str(found.value)
    with as_service_account("engine"):
        # Made by someone who may: an admin still cannot attach it to itself.
        made = iam.create_policy("esc", escalate, scope=WS1)
    with as_user(t.admin) as session:
        refused(lambda: session.attach_policy(made.id, t.admin.id, WS1), made.id)
    with as_user(t.owner) as session:
        session.attach_policy(made.id, t.admin.id, WS1)  # the owner holds it


def run_owner_grants_a_feature_it_lacks(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    with as_service_account("engine"):
        iam.register_catalog(NEXUS)
        iam.put_feature_policies({"owner": ["chat"], "member": ["chat"]})
        every_feature = iam.create_policy(
            "every feature",
            reader(["nexus:UseFeature"], ["${scope}:nexus:feature/*"]),
        )
    with as_user(t.owner) as session:
        refused(
            lambda: session.create_policy(
                "features",
                reader(["nexus:UseFeature"], ["${scope}:nexus:feature/*"]),
                scope=WS1,
            ),
            "nexus:UseFeature",
            "abi:org-1:ws-1:nexus:feature/*",
        )
        refused(
            lambda: session.attach_policy(every_feature.id, t.member.id, WS1),
            "nexus:UseFeature",
        )
        chat = session.create_policy(
            "chat",
            reader(["nexus:UseFeature"], ["${scope}:nexus:feature/chat"]),
            scope=WS1,
        )
        session.attach_policy(chat.id, t.member.id, WS1)


def run_narrowed_key_grants_no_write(iam: IAMService, as_user: AsUser) -> None:
    """A key that reads (plus the right to attach) cannot grant a write role."""
    t = team(iam)
    read_only = [
        {
            "effect": "Allow",
            "actions": ["*:List*", "*:Get*", "*:Query*", "*:Read*", "iam:AttachPolicy"],
            "resources": ["*"],
        }
    ]
    with as_user(t.admin, scope=read_only) as session:
        refused(
            lambda: session.attach_policy(roles.MEMBER, t.colleague.id, WS1),
            "scope of your credential",
        )
        session.attach_policy(roles.VIEWER, t.colleague.id, WS1)
    with as_user(t.admin) as session:
        session.attach_policy(roles.MEMBER, t.colleague.id, WS1)


def run_group_member_exceeds_adder(iam: IAMService, as_user: AsUser) -> None:
    """The second escalation #373 opened: owner attached to a group the admin
    may add itself to."""
    t = team(iam)
    with as_service_account("engine"):
        owners = iam.create_group("owners", scope=WS1)
        iam.attach_policy(roles.OWNER, owners.id, WS1)
        readers = iam.create_group("readers", scope=WS1)
        iam.attach_policy(
            iam.create_policy("r", reader(), scope=WS1).id, readers.id, WS1
        )
    with as_user(t.admin) as session:
        refused(
            lambda: session.add_group_member(owners.id, t.admin.id),
            "builtin.owner",
            "abi:org-1:ws-1",
        )
        session.add_group_member(readers.id, t.member.id)
    with as_service_account("engine"):
        assert iam.list_group_members(owners.id) == []
    with as_user(t.owner) as session:
        session.add_group_member(owners.id, t.admin.id)


def run_hand_attached_feature_policy_is_checked(
    iam: IAMService, as_user: AsUser
) -> None:
    """A feature policy follows a role only where IAM's sync put it: attached to
    a group by hand, it is checked like any other attachment."""
    t = team(iam)
    with as_service_account("engine"):
        iam.register_catalog(NEXUS)
        iam.put_feature_policies(
            {"owner": ["chat", "billing"], "admin": ["chat"], "member": ["chat"]}
        )
        synced = iam.create_group("synced", scope=WS1)
        iam.attach_policy(roles.MEMBER, synced.id, WS1)  # brings features.member
        by_hand = iam.create_group("by hand", scope=WS1)
        iam.attach_policy(roles.MEMBER, by_hand.id, WS1)
    with as_user(t.owner) as session:
        session.attach_policy(roles.feature_policy_id("owner"), by_hand.id, WS1)
    with as_user(t.admin) as session:
        session.add_group_member(synced.id, t.member.id)
        refused(
            lambda: session.add_group_member(by_hand.id, t.member.id),
            roles.feature_policy_id("owner"),
            "abi:org-1:ws-1:nexus:feature/billing",
        )
    with as_user(t.owner) as session:
        session.add_group_member(by_hand.id, t.member.id)


def _inviter(iam: IAMService):
    """May attach member at ws-1, holds a viewer's reach."""
    return custom(
        iam,
        "inviter",
        statement(
            "Allow",
            ["iam:AttachPolicy"],
            [
                "${scope}:iam:attachment/builtin.member/*",
                "${scope}:iam:attachment/builtin.viewer/*",
            ],
        ),
    )


def run_invitation_to_a_role_the_inviter_lacks(
    iam: IAMService, as_user: AsUser
) -> None:
    t = team(iam)
    inviter = _inviter(iam)
    with as_user(inviter) as session:
        refused(
            lambda: session.create_pending_grant(
                "builtin", "eve@example.com", roles.MEMBER, WS1
            ),
            roles.MEMBER,
        )
        session.create_pending_grant("builtin", "eve@example.com", roles.VIEWER, WS1)
    with as_user(t.admin) as session:
        session.create_pending_grant("builtin", "eve@example.com", roles.MEMBER, WS1)


def run_idp_binding(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    inviter = _inviter(iam)
    with as_user(inviter) as session:
        refused(
            lambda: session.bind_idp_group("acme", "Sales", roles.MEMBER, WS1),
            roles.MEMBER,
        )
    with as_service_account("engine"):
        # Refused before the group is made: nothing is left behind.
        assert iam.list_idp_bindings() == []
        assert iam.resolve_idp_groups("acme", ["Sales"]) == []
    with as_user(t.admin) as session:
        binding = session.bind_idp_group("acme", "Sales", roles.MEMBER, WS1)
    with as_user(inviter) as session:
        # Bound already: binding it again grants nothing, so nothing to hold.
        again = session.bind_idp_group("acme", "Sales", roles.MEMBER, WS1)
        assert again.attachment_id == binding.attachment_id


def run_delegated_approver(iam: IAMService, as_user: AsUser) -> None:
    team(iam)
    approver = custom(
        iam,
        "approver",
        statement(
            "Allow",
            ["iam:ApproveManifest", "iam:GetManifest", "iam:ListManifests"],
            ["abi:-:-:iam:manifest/*"],
        ),
        statement("Allow", [QUERY], ["abi:-:-:triple_store:graph/*"]),
        scope=None,
    )
    with as_service_account("engine"):
        account = iam.create_service_account("module/acme/people")
    manifest = document(
        statement(
            "Allow", [QUERY, INSERT], ["abi:-:-:triple_store:graph/${module.id}-*"]
        )
    )
    with use_call_context(
        CallContext(
            principal=Principal(
                id=account.id, kind="service_account", name=account.name
            )
        )
    ):
        iam.submit_manifest("people", "acme", manifest)
    with as_user(approver) as session:
        refused(
            lambda: session.approve_manifest(account.id),
            INSERT,
            "abi:-:-:triple_store:graph/people-*",
        )
        approved = session.approve_manifest(
            account.id,
            document=document(
                statement(
                    "Allow", [QUERY], ["abi:-:-:triple_store:graph/${module.id}-*"]
                )
            ),
        )
        assert approved.status == "approved"


def run_built_in_roles_keep_working(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    with as_service_account("engine"):
        extra = iam.ensure_user("https://idp.example", "extra")
    with as_user(t.admin) as session:
        session.attach_policy(roles.MEMBER, extra.id, WS1)
        session.attach_policy(roles.VIEWER, t.colleague.id, WS1)
        session.attach_policy(roles.ADMIN, t.colleague.id, WS1)
    with as_user(t.owner) as session:
        session.attach_policy(roles.OWNER, extra.id, WS1)
    with as_user(t.org_admin) as session:
        # Through the org-wide role, in each workspace of the org.
        session.attach_policy(roles.ADMIN, extra.id, WS2)
        session.attach_policy(roles.MEMBER, t.member.id, WS2)
        session.attach_policy(roles.MEMBER, extra.id, ORG_SCOPE)


def run_grantable(iam: IAMService, as_user: AsUser) -> None:
    t = team(iam)
    lister = custom(
        iam,
        "lister",
        statement("Allow", ["iam:ListPolicies"], ["abi:*:*:iam:policy/*"]),
        scope=None,
    )
    with as_user(t.root) as session:
        found = _actions(session.grantable(WS1))
        assert found[QUERY] == ("${scope}:*",)
        assert found["iam:AttachPolicy"] == ("${scope}:*",)
    with as_user(t.admin) as session:
        found = _actions(session.grantable(WS1))
        assert found[INSERT] == ("${scope}:triple_store:graph/*",)
        assert "iam:CreatePolicy" in found
        assert all(
            r.startswith("${scope}:iam:attachment/builtin.")
            or r == "${scope}:iam:attachment/pol_*/*"
            for r in found["iam:AttachPolicy"]
        )
        assert (
            "${scope}:iam:attachment/builtin.owner/*" not in found["iam:AttachPolicy"]
        )
        assert _actions(session.grantable(WS2)).get(INSERT) is None
    with as_user(lister) as session:
        assert _actions(session.grantable(WS1)) == {
            "iam:ListPolicies": ("${scope}:iam:policy/*",)
        }


def _actions(catalogs) -> dict[str, tuple[str, ...]]:
    return {a.action: a.resources for c in catalogs for a in c.actions}


SCENARIOS = (
    run_narrower_admin_writes_wider_policy,
    run_admin_cannot_make_itself_owner,
    run_owner_grants_a_feature_it_lacks,
    run_narrowed_key_grants_no_write,
    run_group_member_exceeds_adder,
    run_hand_attached_feature_policy_is_checked,
    run_invitation_to_a_role_the_inviter_lacks,
    run_idp_binding,
    run_delegated_approver,
    run_built_in_roles_keep_working,
    run_grantable,
)
