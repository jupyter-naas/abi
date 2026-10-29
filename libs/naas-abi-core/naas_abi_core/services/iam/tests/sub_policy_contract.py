"""Sub-policies: the acceptance scenarios, run in process
(``IAMService_sub_policies_test.py``) and over NATS
(``IAMSecondaryAdapterNATSClient_test.py``).

``as_user(record)`` is a context manager yielding the ``IIAMService`` a call
makes as that user; the setup is the engine's, on ``iam`` directly. Each
refusal is matched by its type and its message, which cross the wire unchanged.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass

import pytest
from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.IAMPorts import (
    GrantNotHeldError,
    IAMConflictError,
    IAMNotFoundError,
    IIAMService,
    PermissionDeniedError,
    Policy,
    PrincipalRecord,
    RevisionConflictError,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.names import anywhere
from naas_abi_core.services.iam.policy import MAX_DEPTH
from naas_abi_core.services.iam.tests.grant_contract import (
    ORG,
    ORG_SCOPE,
    ORG_WIDE,
    WS1,
    WS2,
    custom,
    team,
)
from naas_abi_core.services.iam.tests.iam_harness import (
    NEXUS,
    document,
    name_in,
    org,
    statement,
)
from naas_abi_core.services.iam.tests.iam_harness import workspace as workspace_name

AsUser = Callable[..., AbstractContextManager[IIAMService]]
USE = "module:UseAgent"
AGENTS = "${scope}/module:agent/*"


def agent(name: str, workspace: str = "ws-1", module: str = "people") -> str:
    return module_scopes.scope_resource(
        "agent", module, name, container=workspace_name(workspace, ORG)
    )


def agents(*names: str, module: str = "people") -> list[str]:
    return [f"${{scope}}/module:agent/{module}/{name}" for name in names]


def allow(resources: list[str], actions: list[str] | None = None) -> dict:
    return document(statement("Allow", actions or [USE], resources))


POLICY_EDITOR = statement(
    "Allow",
    [
        "iam:CreatePolicy",
        "iam:UpdatePolicy",
        "iam:GetPolicy",
        "iam:ListPolicies",
        "iam:DeletePolicy",
    ],
    ["${scope}/iam:policy/*"],
)


@dataclass
class Tree:
    parent: Policy  # P: the platform's, agents a and b
    child: Policy  # S: a sub-policy of P owned by ws-1, every agent
    bob: PrincipalRecord  # holds S only, at ws-1


def tree(iam: IAMService) -> Tree:
    """P allows agents a and b, S allows every agent; Bob holds only S."""
    iam._register_catalog(module_scopes.CATALOG)
    if iam.catalogs.get("nexus") is None:
        iam._register_catalog(NEXUS)
    with as_service_account("api"):
        iam.register_container("nexus", "organization", ORG)
        for ws in ("ws-1", "ws-2"):
            iam.register_container("nexus", "workspace", ws, parent=org(ORG))
    with as_service_account("engine"):
        parent = iam.create_policy("O access", allow(agents("a", "b")))
        child = iam.create_policy(
            "W analysts", allow([AGENTS]), scope=WS1, parent=parent.id
        )
        bob = iam.ensure_user("https://idp.example", "bob")
        iam.attach_policy(child.id, bob.id, WS1)
    return Tree(parent, child, bob)


def _allowed(session: IIAMService, resource: str, action: str = USE) -> bool:
    return session.authorize(action, resource).allowed


# -- what a sub-policy grants ----------------------------------------------------


def run_a_sub_policy_grants_within_its_parent(iam: IAMService, as_user: AsUser):
    t = tree(iam)
    with as_user(t.bob) as session:
        assert _allowed(session, agent("a")) and _allowed(session, agent("b"))
        # S allows every agent: P bounds it to a and b.
        assert not _allowed(session, agent("c"))
        assert not _allowed(session, agent("a", module="crm"))
        # The parent's ${scope} is S's attachment scope: ws-1, never ws-2.
        assert not _allowed(session, agent("a", workspace="ws-2"))
    # Remove b from P: Bob loses it at the next decision.
    with as_service_account("engine"):
        iam.update_policy(t.parent.id, expected_revision=1, document=allow(agents("a")))
    with as_user(t.bob) as session:
        assert _allowed(session, agent("a"))
        decision = session.authorize(USE, agent("b"))
        assert (decision.allowed, decision.reason) == (False, "implicit_deny")


def run_a_deny_of_the_parent_refuses_through_the_sub_policy(
    iam: IAMService, as_user: AsUser
):
    t = tree(iam)
    with as_service_account("engine"):
        iam.update_policy(
            t.parent.id,
            expected_revision=1,
            document=document(
                statement("Allow", [USE], [AGENTS]),
                statement("Deny", [USE], agents("b"), sid="NoB"),
            ),
        )
    with as_user(t.bob) as session:
        assert _allowed(session, agent("a")) and _allowed(session, agent("c"))
        decision = session.authorize(USE, agent("b"))
        assert (decision.allowed, decision.reason) == (False, "explicit_deny")


def run_explain_names_the_chain(iam: IAMService, as_user: AsUser):
    t = team(iam)
    s = tree(iam)
    with as_service_account("engine"):
        middle = iam.create_policy(
            "W agents", allow([AGENTS]), scope=WS1, parent=s.parent.id
        )
        iam.update_policy(s.child.id, expected_revision=1, parent=middle.id)
    with as_user(t.root) as session:
        found = session.explain(USE, agent("a"), principal_id=s.bob.id)
        assert found.allowed and found.statement is not None
        assert found.statement.policy_id == s.child.id
        assert [b.policy_id for b in found.statement.bounded_by] == [
            middle.id,
            s.parent.id,
        ]
        assert found.statement.through == ()
    with as_service_account("engine"):
        iam.update_policy(
            s.parent.id,
            expected_revision=1,
            document=document(
                statement("Allow", [USE], [AGENTS]),
                statement("Deny", [USE], agents("b"), sid="NoB"),
            ),
        )
    with as_user(t.root) as session:
        found = session.explain(USE, agent("b"), principal_id=s.bob.id)
        assert (found.allowed, found.reason) == (False, "explicit_deny")
        assert found.statement is not None
        assert (found.statement.policy_id, found.statement.sid) == (s.parent.id, "NoB")
        assert found.statement.through == (s.child.id, middle.id)


# -- the record and the listing ------------------------------------------------------


def run_the_record_shows_the_parent(iam: IAMService, as_user: AsUser):
    t = team(iam)
    s = tree(iam)
    with as_user(t.root) as session:
        assert session.get_policy(s.child.id).parent_id == s.parent.id
        assert session.get_policy(s.parent.id).parent_id is None
        assert [p.id for p in session.list_sub_policies(s.parent.id)] == [s.child.id]
        assert session.list_sub_policies(s.child.id) == []
    # Whoever may not read the parent learns nothing of it.
    with as_user(s.bob) as session, pytest.raises(IAMNotFoundError):
        session.list_sub_policies(s.parent.id)


# -- refusals -----------------------------------------------------------------------


def run_a_chain_is_refused_when_it_cannot_be(iam: IAMService, as_user: AsUser):
    t = team(iam)
    s = tree(iam)
    with as_user(t.root) as session:
        # A cycle: P under its own sub-policy, or a policy under itself.
        with pytest.raises(ValueError, match="cycle"):
            session.update_policy(s.parent.id, expected_revision=1, parent=s.child.id)
        with pytest.raises(ValueError, match="cycle"):
            session.update_policy(s.parent.id, expected_revision=1, parent=s.parent.id)
        # A parent that does not exist.
        with pytest.raises(IAMNotFoundError, match="pol_"):
            session.create_policy(
                "orphan", allow([AGENTS]), scope=WS1, parent="pol_" + "0" * 26
            )
        # Built-in policies are parents, never sub-policies.
        builtin_child = session.create_policy(
            "viewer, narrowed",
            allow(["${scope}/triple_store:graph/*"], ["triple_store:Query"]),
            scope=WS1,
            parent=roles.VIEWER,
        )
        assert builtin_child.parent_id == roles.VIEWER
        with pytest.raises(IAMConflictError, match="managed"):
            session.update_policy(roles.VIEWER, expected_revision=1, parent=s.parent.id)
        # Deeper than MAX_DEPTH: the root is at depth 1.
        chain = [s.parent]
        for depth in range(2, MAX_DEPTH + 1):
            chain.append(
                session.create_policy(
                    f"depth {depth}", allow([AGENTS]), scope=WS1, parent=chain[-1].id
                )
            )
        with pytest.raises(ValueError, match="deeper than 8"):
            session.create_policy(
                "too deep", allow([AGENTS]), scope=WS1, parent=chain[-1].id
            )
        # Moving S (depth 2) under the deepest one would put it at depth 9.
        with pytest.raises(ValueError, match="deeper than 8"):
            session.update_policy(s.child.id, expected_revision=1, parent=chain[-1].id)
        # A stale revision changes nothing.
        with pytest.raises(RevisionConflictError):
            session.update_policy(s.child.id, expected_revision=7, parent="")
        assert session.get_policy(s.child.id).parent_id == s.parent.id


def run_a_sub_policy_is_owned_at_its_parent_or_below(iam: IAMService, as_user: AsUser):
    t = team(iam)
    s = tree(iam)
    with as_user(t.root) as session:
        org_policy = session.create_policy("org", allow([AGENTS]), scope=ORG_SCOPE)
        ws_policy = session.create_policy("ws", allow([AGENTS]), scope=WS1)
        # A platform policy's: the platform or any container.
        for owner in (None, ORG_SCOPE, WS2):
            session.create_policy("p", allow([AGENTS]), scope=owner, parent=s.parent.id)
        # An org's: the org or a container in it (one of its workspaces).
        session.create_policy(
            "o", allow([AGENTS]), scope=ORG_SCOPE, parent=org_policy.id
        )
        session.create_policy("o", allow([AGENTS]), scope=WS2, parent=org_policy.id)
        with pytest.raises(
            ValueError, match=re.escape(f"owned by {ORG_SCOPE} or below")
        ):
            session.create_policy("o", allow([AGENTS]), parent=org_policy.id)
        # A workspace's: that workspace or a container inside it.
        session.create_policy("w", allow([AGENTS]), scope=WS1, parent=ws_policy.id)
        for owner in (WS2, ORG_SCOPE):
            with pytest.raises(ValueError, match=re.escape(f"owned by {WS1} or below")):
                session.create_policy(
                    "w", allow([AGENTS]), scope=owner, parent=ws_policy.id
                )


def run_a_parent_with_sub_policies_is_not_deleted(iam: IAMService, as_user: AsUser):
    t = team(iam)
    s = tree(iam)
    with as_user(t.root) as session:
        with pytest.raises(IAMConflictError) as refused:
            session.delete_policy(s.parent.id)
        assert s.child.id in str(refused.value) and "W analysts" in str(refused.value)
        # Re-parented, S frees P; then S is deleted once detached.
        session.update_policy(s.child.id, expected_revision=1, parent="")
        session.delete_policy(s.parent.id)
        session.detach_policy(s.child.id, s.bob.id, WS1)
        session.delete_policy(s.child.id)
    with as_service_account("engine"):
        # Deleting the container that owns a parent deletes its sub-policies first.
        parent = iam.create_policy("ws parent", allow([AGENTS]), scope=WS1)
        child = iam.create_policy(
            "ws child", allow([AGENTS]), scope=WS1, parent=parent.id
        )
        iam.create_policy("grandchild", allow([AGENTS]), scope=WS1, parent=child.id)
    with as_service_account("api"):
        iam.delete_container("nexus", "workspace", "ws-1")
    with as_service_account("engine"):
        for gone in (parent.id, child.id, s.child.id):
            with pytest.raises(IAMNotFoundError):
                iam.get_policy(gone)


# -- derive only from what you hold ---------------------------------------------------


def run_derive_only_from_what_you_hold(iam: IAMService, as_user: AsUser):
    t = team(iam)
    s = tree(iam)
    with as_service_account("engine"):
        # P is held by the org's admins below it: above every workspace of the org.
        iam.attach_policy(s.parent.id, t.org_admin.id, ORG_WIDE)
        # Ws-1's admin holds agent a through a policy of its own (no role does).
        held = iam.create_policy("a, for ws-1's admin", allow(agents("a")), scope=WS1)
        iam.attach_policy(held.id, t.admin.id, WS1)
    with as_user(t.org_admin) as session:
        made = session.create_policy(
            "analysts", allow(agents("a")), scope=WS1, parent=s.parent.id
        )
        assert made.parent_id == s.parent.id
    # Ws-1's admin does not hold P: the refusal names it and the scope.
    with as_user(t.admin) as session:
        with pytest.raises(PermissionDeniedError) as refused:
            session.create_policy(
                "mine", allow(agents("a")), scope=WS1, parent=s.parent.id
            )
        assert not isinstance(refused.value, GrantNotHeldError)
        assert s.parent.id in str(refused.value)
        assert f"attached to you or to one of your groups at {WS1} " in str(
            refused.value
        )
        # Nor may it move a policy of its own under P.
        own = session.create_policy("own", allow(agents("a")), scope=WS1)
        with pytest.raises(PermissionDeniedError, match=s.parent.id):
            session.update_policy(own.id, expected_revision=1, parent=s.parent.id)
    # Held through a group, at the workspace: enough for a policy of the workspace.
    with as_service_account("engine"):
        group = iam.create_group("leads", scope=WS1)
        iam.add_group_member(group.id, t.admin.id)
        iam.attach_policy(s.parent.id, group.id, WS1)
    with as_user(t.admin) as session:
        session.update_policy(own.id, expected_revision=1, parent=s.parent.id)
    # Held at ws-1 is not held at the org: an org's policy is not derived from it.
    with as_service_account("engine"):
        org_lead = iam.ensure_user("https://idp.example", "org-lead")
        iam.attach_policy(roles.ADMIN, org_lead.id, ORG_SCOPE)
        iam.attach_policy(s.parent.id, org_lead.id, WS1)
    with (
        as_user(org_lead) as session,
        pytest.raises(PermissionDeniedError, match=re.escape(f"{ORG_SCOPE} or above")),
    ):
        session.create_policy(
            "org", allow(agents("a")), scope=ORG_SCOPE, parent=s.parent.id
        )
    # Held through a sub-policy of P is not holding P.
    with as_service_account("engine"):
        lead = iam.ensure_user("https://idp.example", "lead")
        iam.attach_policy(roles.ADMIN, lead.id, WS1)
        iam.attach_policy(s.child.id, lead.id, WS1)
    with as_user(lead) as session, pytest.raises(PermissionDeniedError):
        session.create_policy("x", allow(agents("a")), scope=WS1, parent=s.parent.id)
    # The platform admin derives from any policy.
    with as_user(t.root) as session:
        session.create_policy("root's", allow([AGENTS]), scope=WS2, parent=s.parent.id)


def run_grant_only_what_you_hold_reads_the_chain(iam: IAMService, as_user: AsUser):
    s = tree(iam)
    with as_service_account("engine"):
        held = iam.create_policy("held", allow(agents("a", "b")), scope=WS1)
    editor = custom(iam, "editor", POLICY_EDITOR)
    with as_service_account("engine"):
        iam.attach_policy(held.id, editor.id, WS1)
    with as_user(editor) as session:
        # Every agent, within `held`: a and b, which the editor holds.
        derived = session.create_policy(
            "every agent within held", allow([AGENTS]), scope=WS1, parent=held.id
        )
        # Without the parent it is every agent: not held.
        with pytest.raises(GrantNotHeldError, match="module:agent"):
            session.update_policy(derived.id, expected_revision=1, parent="")
        with pytest.raises(GrantNotHeldError, match="module:agent"):
            session.create_policy("every agent", allow([AGENTS]), scope=WS1)
    # A Deny of the giver still refuses what the chain lets through.
    with as_service_account("engine"):
        no_b = iam.create_policy(
            "no b", document(statement("Deny", [USE], agents("b"))), scope=WS1
        )
        iam.attach_policy(no_b.id, editor.id, WS1)
    with as_user(editor) as session:
        with pytest.raises(GrantNotHeldError, match=no_b.id):
            session.create_policy("again", allow([AGENTS]), scope=WS1, parent=held.id)
        session.create_policy("a only", allow(agents("a")), scope=WS1, parent=held.id)
    # What a caller holds through a sub-policy is bounded by its chain: Bob holds
    # S, every agent within P's a and b.
    with as_service_account("engine"):
        iam.attach_policy(
            iam.create_policy("bob edits", document(POLICY_EDITOR)).id,
            s.bob.id,
            WS1,
        )
    with as_user(s.bob) as session:
        session.create_policy("a", allow(agents("a")), scope=WS1)
        with pytest.raises(GrantNotHeldError, match="module:agent/people/c"):
            session.create_policy("c", allow(agents("c")), scope=WS1)


def run_widening_a_parent_is_checked_below_it(iam: IAMService, as_user: AsUser):
    """An org's editor holds agents at the org's own level only: widening its
    policy would widen a workspace's sub-policy beyond what it holds there."""
    tree(iam)
    org_editor = custom(
        iam,
        "org-editor",
        POLICY_EDITOR,
        statement("Allow", [USE], [AGENTS]),
        scope=ORG_SCOPE,
    )
    with as_user(org_editor) as session:
        parent = session.create_policy(
            "org agents", allow(agents("a", "b")), scope=ORG_SCOPE
        )
    with as_service_account("engine"):
        child = iam.create_policy(
            "ws agents", allow([AGENTS]), scope=WS1, parent=parent.id
        )
    with as_user(org_editor) as session:
        with pytest.raises(GrantNotHeldError) as refused:
            session.update_policy(
                parent.id, expected_revision=1, document=allow([AGENTS])
            )
        assert child.id in str(refused.value) and WS1 in str(refused.value)
        # Narrowing it never is: what is below it only narrows with it.
        session.update_policy(
            parent.id, expected_revision=1, document=allow(agents("a"))
        )


def run_re_parenting_under_a_deny_beyond_scope_is_attaching_it(
    iam: IAMService, as_user: AsUser
):
    """A workspace admin's own policy, attached at its workspace, moved under a
    platform policy that denies in every org: as attaching it would be, refused
    to anyone who may not attach it unscoped."""
    t = team(iam)
    s = tree(iam)
    with as_service_account("engine"):
        guarded = iam.create_policy(
            "agents, no secret anywhere",
            document(
                statement("Allow", [USE], [AGENTS]),
                statement("Deny", [USE], anywhere("module:agent/people/secret")),
            ),
        )
        iam.attach_policy(guarded.id, t.admin.id, WS1)
    with as_user(t.admin) as session:
        own = session.create_policy("own", allow(agents("a")), scope=WS1)
        session.attach_policy(own.id, t.member.id, WS1)
        with pytest.raises(PermissionDeniedError, match="unscoped"):
            session.update_policy(own.id, expected_revision=1, parent=guarded.id)
        assert session.get_policy(own.id).parent_id is None
        mid = session.create_policy("mid", allow(agents("a")), scope=WS1)
    # A policy below the one moved carries the Deny too: the same rule for it.
    with as_service_account("engine"):
        below = iam.create_policy("below", allow(agents("a")), scope=WS1, parent=mid.id)
        iam.attach_policy(below.id, t.member.id, WS1)
    with (
        as_user(t.admin) as session,
        pytest.raises(PermissionDeniedError, match=below.id),
    ):
        session.update_policy(mid.id, expected_revision=1, parent=guarded.id)
    # The platform admin may: they attach anything unscoped.
    with as_user(t.root) as session:
        session.update_policy(mid.id, expected_revision=1, parent=guarded.id)
        session.update_policy(own.id, expected_revision=1, parent=guarded.id)
    assert s.child.parent_id == s.parent.id


def run_a_refusal_names_only_what_the_caller_may_see(iam: IAMService, as_user: AsUser):
    """Deleting a parent names the sub-policies the caller may list and counts
    the rest; a parent the caller may not derive from is refused before its
    owner is said."""
    t = team(iam)
    s = tree(iam)
    deleter = custom(
        iam,
        "deleter",
        statement(
            "Allow",
            ["iam:DeletePolicy", "iam:GetPolicy", "iam:ListPolicies"],
            ["abi:iam:policy/*"],
        ),
        scope=None,
    )
    with as_service_account("engine"):
        visible = iam.create_policy("platform sub", allow([AGENTS]), parent=s.parent.id)
    with as_user(deleter) as session, pytest.raises(IAMConflictError) as refused:
        session.delete_policy(s.parent.id)
    message = str(refused.value)
    assert visible.id in message and "1 you may not list" in message
    assert s.child.id not in message and "W analysts" not in message
    with as_service_account("engine"):
        elsewhere = iam.create_policy("ws-2's", allow([AGENTS]), scope=WS2)
    with as_user(t.admin) as session, pytest.raises(PermissionDeniedError) as denied:
        session.create_policy("x", allow([AGENTS]), scope=WS1, parent=elsewhere.id)
    assert WS2 not in str(denied.value) and not isinstance(
        denied.value, GrantNotHeldError
    )


def run_lifting_a_parent_s_deny_is_checked_below_it(iam: IAMService, as_user: AsUser):
    """A Deny of a parent refuses through its sub-policies: lifting or narrowing
    it widens them, so it is checked where they are attached. An admin of the
    org's own level holds nothing in its workspaces."""
    t = team(iam)
    query = "triple_store:Query"
    graphs = "${scope}/triple_store:graph/*"
    secret = name_in(WS1, "triple_store:graph/secret")

    def guarded(denied: str) -> dict:
        return document(
            statement("Allow", [query], [graphs]),
            statement("Deny", [query], [f"${{scope}}/triple_store:graph/{denied}"]),
        )

    with as_service_account("engine"):
        parent = iam.create_policy("org graphs", guarded("secret"), scope=ORG_SCOPE)
        child = iam.create_policy(
            "ws graphs",
            document(statement("Allow", [query], [graphs])),
            scope=WS1,
            parent=parent.id,
        )
        bob = iam.ensure_user("https://idp.example", "bob")
        iam.attach_policy(child.id, bob.id, WS1)
        eve = iam.ensure_user("https://idp.example", "eve")
        iam.attach_policy(roles.ADMIN, eve.id, ORG_SCOPE)
    with as_user(bob) as session:
        assert not session.authorize(query, secret).allowed
    with as_user(eve) as session:
        assert not session.authorize(query, secret).allowed
        lifted = document(statement("Allow", [query], [graphs]))
        with pytest.raises(GrantNotHeldError) as refused:
            session.update_policy(parent.id, expected_revision=1, document=lifted)
        assert child.id in str(refused.value) and WS1 in str(refused.value)
        # Narrowed to another graph, the Deny lets the secret through too.
        with pytest.raises(GrantNotHeldError, match=child.id):
            session.update_policy(
                parent.id, expected_revision=1, document=guarded("secret-old")
            )
        # A Deny added narrows: never refused for what is below.
        session.update_policy(
            parent.id,
            expected_revision=1,
            document=document(
                statement("Allow", [query], [graphs]),
                statement("Deny", [query], ["${scope}/triple_store:graph/secret"]),
                statement("Deny", [query], ["${scope}/triple_store:graph/hr"]),
            ),
        )
    with as_user(bob) as session:
        assert not session.authorize(query, secret).allowed
    # Whoever holds the data there (the platform admin) lifts it.
    with as_user(t.root) as session:
        session.update_policy(
            parent.id,
            expected_revision=2,
            document=document(statement("Allow", [query], [graphs])),
        )
    with as_user(bob) as session:
        assert session.authorize(query, secret).allowed


SCENARIOS = (
    run_a_sub_policy_grants_within_its_parent,
    run_a_deny_of_the_parent_refuses_through_the_sub_policy,
    run_explain_names_the_chain,
    run_the_record_shows_the_parent,
    run_a_chain_is_refused_when_it_cannot_be,
    run_a_sub_policy_is_owned_at_its_parent_or_below,
    run_a_parent_with_sub_policies_is_not_deleted,
    run_derive_only_from_what_you_hold,
    run_grant_only_what_you_hold_reads_the_chain,
    run_widening_a_parent_is_checked_below_it,
    run_re_parenting_under_a_deny_beyond_scope_is_attaching_it,
    run_a_refusal_names_only_what_the_caller_may_see,
    run_lifting_a_parent_s_deny_is_checked_below_it,
)
