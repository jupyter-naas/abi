"""The evaluation rules of RFC §5, through ``IAMService`` and the policy authorizer."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import ANONYMOUS, use_call_context
from naas_abi_core.services.iam.adapters.secondary.authorizer__allow_all import (
    AllowAllAuthorizer,
)
from naas_abi_core.services.iam.adapters.secondary.IAMStoreMemory import IAMStoreMemory
from naas_abi_core.services.iam.IAMPorts import (
    IAMNotFoundError,
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import graph, statement

QUERY = "triple_store:Query"
INSERT = "triple_store:Insert"


class GraphNotFound(LookupError):
    pass


# -- deny by default --------------------------------------------------------------


def test_nothing_is_allowed_without_a_matching_allow(h):
    bob = h.user()
    assert not h.allowed(QUERY, graph("sales"), bob)
    with use_call_context(ANONYMOUS):
        decision = h.iam.authorize(QUERY, graph("sales"))
    assert (decision.allowed, decision.visible, decision.reason) == (
        False,
        False,
        "implicit_deny",
    )


def test_a_known_service_account_without_policies_is_denied(h):
    ci = h.service_account("ci/nightly")
    assert not h.allowed(QUERY, graph("sales"), ci)
    # Its name, as Stage 1 tokens name it, resolves to the same record.
    assert not h.allowed(QUERY, graph("sales"), actor="ci/nightly")


def test_an_allow_on_another_action_or_resource_allows_nothing_else(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", [QUERY], [graph("sales")]))
    assert h.allowed(QUERY, graph("sales"), bob)
    assert not h.allowed(INSERT, graph("sales"), bob)
    assert not h.allowed(QUERY, graph("hr"), bob)


# -- an explicit Deny wins -------------------------------------------------------------


def test_an_explicit_deny_beats_any_allow(h):
    bob = h.user()
    h.grant(
        bob.id,
        statement("Allow", ["triple_store:*"], ["*"]),
        statement("Deny", [QUERY], [graph("secret")], sid="NoSecrets"),
    )
    assert h.allowed(QUERY, graph("sales"), bob)
    with h.as_(bob):
        decision = h.iam.authorize(QUERY, graph("secret"))
    assert (decision.allowed, decision.reason) == (False, "explicit_deny")


def test_a_deny_through_a_group_beats_a_direct_allow(h):
    bob = h.user()
    sales = h.group("sales")
    h.admin("add_group_member", sales.id, bob.id)
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    h.grant(sales.id, statement("Deny", [QUERY], [graph("hr")]))
    assert h.allowed(QUERY, graph("sales"), bob)
    assert not h.allowed(QUERY, graph("hr"), bob)


def test_platform_admin_is_an_attached_policy_and_a_deny_still_wins(h):
    root = h.user("root")
    assert not h.allowed(QUERY, graph("x"), root)
    h.attach("builtin.platform_admin", root.id)
    assert h.allowed(QUERY, graph("x"), root)
    h.grant(root.id, statement("Deny", [QUERY], [graph("x")]))
    assert not h.allowed(QUERY, graph("x"), root)


# -- wildcards -----------------------------------------------------------------------------


def test_action_wildcards(h):
    bob = h.user()
    h.grant(
        bob.id,
        statement("Allow", ["triple_store:Query*", "triple_store:?nsert"], ["*"]),
    )
    assert h.allowed("triple_store:Query", graph("a"), bob)
    assert h.allowed("triple_store:QueryStream", graph("a"), bob)
    assert h.allowed(INSERT, graph("a"), bob)
    assert not h.allowed("triple_store:ListGraphs", graph("a"), bob)
    # Matching is case-sensitive.
    assert not h.allowed("triple_store:query", graph("a"), bob)


def test_resource_wildcards_cross_segments_and_question_marks_match_one_char(h):
    bob = h.user()
    h.grant(
        bob.id,
        statement("Allow", [QUERY], ["abi:org-1:*"]),
        statement("Allow", [INSERT], ["abi:org-2:ws-?:triple_store:graph/*"]),
    )
    assert h.allowed(QUERY, graph("a", "org-1", "ws-9"), bob)
    assert h.allowed(QUERY, "abi:org-1:-:triple_store:graph/a", bob)
    # "abi:org-1:*" stops at the field: org-10 is another org.
    assert not h.allowed(QUERY, graph("a", "org-10", "ws-1"), bob)
    assert h.allowed(INSERT, graph("a", "org-2", "ws-1"), bob)
    assert not h.allowed(INSERT, graph("a", "org-2", "ws-12"), bob)


def test_encoded_ids_never_read_as_wildcards(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", [QUERY], [graph("http%3A%2F%2Fx%2Fsales-*")]))
    assert h.allowed(QUERY, graph("http%3A%2F%2Fx%2Fsales-q3"), bob)
    assert not h.allowed(QUERY, graph("http%3A%2F%2Fx%2Fhr"), bob)
    # A literal "*" in an id is %2A: the pattern's * still means "anything".
    assert h.allowed(QUERY, graph("http%3A%2F%2Fx%2Fsales-%2A"), bob)


# -- groups and IdP groups ---------------------------------------------------------------------


def test_static_group_attachments_reach_members(h):
    bob, alice = h.user("bob"), h.user("alice")
    sales = h.group("sales")
    h.admin("add_group_member", sales.id, bob.id)
    h.grant(sales.id, statement("Allow", [QUERY], [graph("sales")]))
    assert h.allowed(QUERY, graph("sales"), bob)
    assert not h.allowed(QUERY, graph("sales"), alice)
    h.admin("remove_group_member", sales.id, bob.id)
    assert not h.allowed(QUERY, graph("sales"), bob)


def test_idp_groups_reach_the_user_through_the_token(h):
    """An IdP group claim maps to a group; the token's grp carries it (RFC §2)."""
    bob = h.user()
    readers = h.group("graph-readers")
    writers = h.group("graph-writers")
    h.admin("map_idp_group", "acme", "Readers", readers.id)
    h.admin("map_idp_group", "acme", "Writers", writers.id)
    h.grant(readers.id, statement("Allow", [QUERY], [graph("a")]))
    h.grant(writers.id, statement("Allow", [INSERT], [graph("b")]))
    groups = frozenset(h.iam.resolve_idp_groups("acme", ["Readers", "Writers"]))
    assert groups == {readers.id, writers.id}
    assert h.allowed(QUERY, graph("a"), bob, groups=groups)
    assert h.allowed(INSERT, graph("b"), bob, groups=groups)
    assert not h.allowed(INSERT, graph("a"), bob, groups=groups)
    assert not h.allowed(QUERY, graph("a"), bob)


def test_a_service_account_can_read_one_graph_and_write_another(h):
    etl = h.service_account("ci/etl")
    h.grant(
        etl.id,
        statement("Allow", [QUERY], [graph("a")]),
        statement("Allow", [INSERT], [graph("b")]),
    )
    assert h.allowed(QUERY, graph("a"), etl)
    assert h.allowed(INSERT, graph("b"), etl)
    assert not h.allowed(INSERT, graph("a"), etl)
    assert not h.allowed(QUERY, graph("b"), etl)


def test_a_suspended_or_deleted_group_grants_nothing(h):
    bob = h.user()
    sales = h.group()
    h.admin("add_group_member", sales.id, bob.id)
    h.grant(sales.id, statement("Allow", [QUERY], ["*"]))
    assert h.allowed(QUERY, graph("a"), bob, groups=frozenset({sales.id}))
    h.admin("delete_group", sales.id)
    assert not h.allowed(QUERY, graph("a"), bob)
    assert not h.allowed(QUERY, graph("a"), bob, groups=frozenset({sales.id}))


# -- suspension -----------------------------------------------------------------------------------


def test_suspension_denies_everything_at_once_and_resume_restores(h):
    bob = h.user()
    h.attach("builtin.platform_admin", bob.id)
    assert h.allowed(QUERY, graph("a"), bob)
    h.admin("suspend_principal", bob.id)
    with h.as_(bob):
        decision = h.iam.authorize(QUERY, graph("a"))
    assert (decision.allowed, decision.visible, decision.reason) == (
        False,
        False,
        "suspended",
    )
    h.admin("resume_principal", bob.id)
    assert h.allowed(QUERY, graph("a"), bob)


def test_a_suspended_user_is_denied_even_through_a_broad_actor(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", [QUERY], ["*"]))
    assert h.allowed(QUERY, graph("a"), actor="api", on_behalf_of=bob)
    h.admin("suspend_principal", bob.id)
    assert not h.allowed(QUERY, graph("a"), actor="api", on_behalf_of=bob)


# -- on behalf of: both must be allowed -----------------------------------------------------------


def test_on_behalf_of_is_an_intersection(h):
    bob = h.user()
    agent = h.service_account("module/acme/agent")
    h.grant(bob.id, statement("Allow", [QUERY], [graph("g")]))
    h.grant(agent.id, statement("Allow", [QUERY, INSERT], [graph("g")]))
    assert h.allowed(QUERY, graph("g"), agent, on_behalf_of=bob)
    # The agent may write G, the user may only read it.
    assert not h.allowed(INSERT, graph("g"), agent, on_behalf_of=bob)
    # The broad api actor is bounded by the user too.
    assert not h.allowed(INSERT, graph("g"), actor="api", on_behalf_of=bob)


def test_user_variable_lets_an_actor_policy_name_the_user_it_serves(h):
    bob, alice = h.user("bob"), h.user("alice")
    agent = h.service_account("module/acme/notes")
    h.grant(
        agent.id,
        statement(
            "Allow", ["activity_log:Query"], ["abi:-:-:activity_log:actor/${user.id}"]
        ),
    )
    actor = f"abi:-:-:activity_log:actor/{bob.id}"
    # builtin.self lets bob read his own activity; the agent's policy names him.
    assert h.allowed("activity_log:Query", actor, agent, on_behalf_of=bob)
    assert not h.allowed(
        "activity_log:Query",
        f"abi:-:-:activity_log:actor/{alice.id}",
        agent,
        on_behalf_of=bob,
    )
    # Without a user ${user.id} is unresolved and the statement matches nothing.
    assert not h.allowed("activity_log:Query", actor, agent)


def test_principal_variable_resolves_to_the_member_not_the_group(h):
    bob, alice = h.user("bob"), h.user("alice")
    team = h.group("team")
    for member in (bob, alice):
        h.admin("add_group_member", team.id, member.id)
    h.grant(
        team.id,
        statement(
            "Allow",
            ["activity_log:ReadNote"],
            ["abi:org-1:ws-1:activity_log:note/${principal.id}/*"],
        ),
    )
    note = "abi:org-1:ws-1:activity_log:note/{}/n1"
    assert h.allowed("activity_log:ReadNote", note.format(bob.id), bob)
    assert not h.allowed("activity_log:ReadNote", note.format(alice.id), bob)
    assert not h.allowed("activity_log:ReadNote", note.format(team.id), bob)


# -- token narrowing ---------------------------------------------------------------------------------


def test_a_narrowed_token_only_narrows(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", [QUERY, INSERT], ["*"]))
    narrowing = (
        {"effect": "Allow", "actions": [QUERY], "resources": [graph("a")]},
        # A Deny in a token is refused at issue; here it simply matches nothing.
        {"effect": "Deny", "actions": [QUERY], "resources": [graph("a")]},
    )
    assert h.allowed(QUERY, graph("a"), bob, scope=narrowing)
    assert not h.allowed(QUERY, graph("b"), bob, scope=narrowing)
    assert not h.allowed(INSERT, graph("a"), bob, scope=narrowing)
    # Narrowing never adds: the token cannot reach what the user cannot.
    widening = ({"effect": "Allow", "actions": ["*"], "resources": ["*"]},)
    assert not h.allowed("triple_store:DropGraph", graph("a"), bob, scope=widening)


# -- sealed resources ---------------------------------------------------------------------------------


def test_sealed_resources_open_to_their_owner_only(h):
    root = h.user("root")
    h.attach("builtin.platform_admin", root.id)
    signing_key = "abi:-:-:secret:secret/iam%2Fsigning-keys%2Fk1"
    idp_doc = "abi:-:-:document:document/idp/users/u1"
    with h.as_(root):
        decision = h.iam.authorize("secret:Get", signing_key)
    assert (decision.allowed, decision.reason) == (False, "sealed")
    assert not h.allowed("document:Get", idp_doc, actor="api")
    assert not h.allowed("document:Get", idp_doc, actor="engine")
    assert h.allowed("document:Get", idp_doc, actor="idp")
    assert h.allowed("secret:Get", signing_key, actor="engine")
    # OBO never unlocks a seal: the owner must be the actor.
    assert not h.allowed("secret:Get", signing_key, actor="api", on_behalf_of=root)


# -- lists ----------------------------------------------------------------------------------------------


def test_filter_returns_the_allowed_subset_in_order_and_drops_denied_items(h):
    bob = h.user()
    h.grant(
        bob.id,
        statement(
            "Allow",
            ["triple_store:ListGraphs"],
            ["abi:org-1:ws-1:triple_store:graph/*"],
        ),
        statement("Deny", ["triple_store:ListGraphs"], [graph("secret")]),
    )
    items = [graph("b"), graph("secret"), graph("a", workspace="ws-2"), graph("a")]
    with h.as_(bob):
        result = h.iam.filter("triple_store:ListGraphs", items)
    assert result.allowed == [graph("b"), graph("a")]
    assert result.prefix_hints == ["abi:org-1:ws-1:triple_store:graph/"]


def test_filter_hints(h):
    bob = h.user()
    with h.as_(bob):
        assert h.iam.filter(QUERY, [graph("a")]).prefix_hints == []
    h.grant(
        bob.id,
        statement(
            "Allow", [QUERY], [graph("sales-*"), graph("sales-q3-*"), graph("hr")]
        ),
    )
    with h.as_(bob):
        assert h.iam.filter(QUERY, []).prefix_hints == [
            graph("hr"),
            graph("sales-"),
        ]
    # On behalf of a user, the user's bounded hints win over api's "anything".
    with h.as_(actor="api", on_behalf_of=bob):
        assert h.iam.filter(QUERY, []).prefix_hints == [graph("hr"), graph("sales-")]
    with h.as_(actor="api"):
        assert h.iam.filter(QUERY, []).prefix_hints == [""]


# -- not found or permission denied ---------------------------------------------------------------------


def test_visible_resources_are_denied_and_invisible_ones_not_found(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", [QUERY], [graph("a")]))
    with h.as_(bob):
        decision = h.iam.authorize(INSERT, graph("a"))
        assert (decision.allowed, decision.visible) == (False, True)
        with pytest.raises(PermissionDeniedError) as denied:
            h.iam.require(INSERT, graph("a"), not_found=GraphNotFound)
        assert denied.value.action == INSERT and denied.value.resource == graph("a")
        assert isinstance(denied.value, PermissionError)
        # No access at all: the service's own not-found, as if it did not exist.
        with pytest.raises(GraphNotFound):
            h.iam.require(INSERT, graph("b"), not_found=GraphNotFound)
        with pytest.raises(ResourceNotFoundError):
            h.iam.require(QUERY, graph("b"))
        h.iam.require(QUERY, graph("a"))


def test_a_create_on_a_name_the_caller_can_see_is_denied_otherwise_not_found(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", ["triple_store:ListGraphs"], [graph("*")]))
    with h.as_(bob), pytest.raises(PermissionDeniedError):
        h.iam.require("triple_store:CreateGraph", graph("new"))
    carol = h.user("carol")
    with h.as_(carol), pytest.raises(GraphNotFound):
        h.iam.require("triple_store:CreateGraph", graph("new"), not_found=GraphNotFound)


# -- explain ------------------------------------------------------------------------------------------------


def test_explain_names_the_deciding_statement(h):
    bob = h.user()
    sales = h.group()
    h.admin("add_group_member", sales.id, bob.id)
    allow = h.grant(bob.id, statement("Allow", [QUERY], ["*"], sid="ReadAll"))
    deny = h.grant(sales.id, statement("Deny", [QUERY], [graph("hr")], sid="NoHr"))

    with h.as_(actor="engine"):
        allowed = h.iam.explain(QUERY, graph("a"), principal_id=bob.id)
        denied = h.iam.explain(QUERY, graph("hr"), principal_id=bob.id)
        nothing = h.iam.explain(INSERT, graph("a"), principal_id=bob.id)

    assert (allowed.allowed, allowed.reason) == (True, "allow")
    assert allowed.statement is not None
    assert (allowed.statement.policy_id, allowed.statement.sid) == (allow.id, "ReadAll")
    assert allowed.statement.statement_index == 0
    assert allowed.statement.side == "actor" and allowed.statement.attachment_id

    assert (denied.allowed, denied.reason) == (False, "explicit_deny")
    assert denied.statement is not None
    assert (denied.statement.policy_id, denied.statement.sid) == (deny.id, "NoHr")
    assert denied.statement.via_group == sales.id

    assert (nothing.allowed, nothing.reason, nothing.statement) == (
        False,
        "implicit_deny",
        None,
    )


def test_explain_shows_whose_side_decided_on_behalf_of_a_user(h):
    bob = h.user()
    h.grant(bob.id, statement("Deny", [INSERT], ["*"], sid="ReadOnly"))
    h.attach("builtin.platform_admin", bob.id)
    from naas_abi_core.engine.call_context import CallContext, Principal

    ctx = CallContext(
        principal=Principal(id="api", kind="service_account", name="api"),
        on_behalf_of=Principal(id=bob.id, kind="user"),
    )
    explanation = h.iam.authorizer.explain(ctx, INSERT, graph("a"))
    assert explanation.reason == "explicit_deny"
    assert explanation.statement is not None
    assert (explanation.statement.side, explanation.statement.sid) == (
        "user",
        "ReadOnly",
    )


def test_explain_needs_iam_explain_on_the_principal(h):
    bob, carol = h.user("bob"), h.user("carol")
    with h.as_(carol), pytest.raises(IAMNotFoundError):
        h.iam.explain(QUERY, graph("a"), principal_id=bob.id)
    # Carol sees her own principal (builtin.self), so she is denied, not "not found".
    with h.as_(carol), pytest.raises(PermissionDeniedError):
        h.iam.explain(QUERY, graph("a"))
    h.grant(carol.id, statement("Allow", ["iam:Explain"], ["abi:-:-:iam:principal/*"]))
    with h.as_(carol):
        assert h.iam.explain(QUERY, graph("a"), principal_id=bob.id).allowed is False


# -- built-in roles ----------------------------------------------------------------------------------------------


def test_viewer_on_a_workspace_reads_it_and_nothing_else(h):
    bob = h.user()
    h.attach("builtin.viewer", bob.id, "abi:org-1:ws-1")
    assert h.allowed(QUERY, graph("a"), bob)
    assert h.allowed("triple_store:ListGraphs", graph("a"), bob)
    assert not h.allowed(INSERT, graph("a"), bob)
    assert not h.allowed(QUERY, graph("a", workspace="ws-2"), bob)
    # Platform types come from the companion policy, not from the scope.
    with h.as_(bob):
        explanation = h.iam.authorizer.explain(
            h.context(bob), "triple_store:QueryView", "abi:-:-:triple_store:view/v"
        )
    assert explanation.allowed
    assert explanation.statement is not None
    assert explanation.statement.policy_id == "builtin.platform.viewer"


def test_roles_are_cumulative(h):
    bob = h.user()
    h.attach("builtin.member", bob.id, "abi:org-1:ws-1")
    assert h.allowed(QUERY, graph("a"), bob)
    assert h.allowed(INSERT, graph("a"), bob)
    assert not h.allowed("triple_store:DropGraph", graph("a"), bob)
    h.attach("builtin.admin", bob.id, "abi:org-1:ws-2")
    assert h.allowed("triple_store:DropGraph", graph("a", workspace="ws-2"), bob)


def test_org_wide_and_org_level_scopes(h):
    bob, carol = h.user("bob"), h.user("carol")
    h.attach("builtin.viewer", bob.id, "abi:org-1:*")
    assert h.allowed(QUERY, graph("a", workspace="ws-7"), bob)
    assert not h.allowed(QUERY, graph("a", org="org-2"), bob)
    h.attach("builtin.viewer", carol.id, "abi:org-1:-")
    assert h.allowed(QUERY, "abi:org-1:-:triple_store:graph/a", carol)
    assert not h.allowed(QUERY, graph("a"), carol)


def test_only_owners_grant_or_remove_owners(h):
    admin, owner, bob = h.user("admin"), h.user("owner"), h.user("bob")
    scope = "abi:org-1:ws-1"
    h.attach("builtin.admin", admin.id, scope)
    h.attach("builtin.owner", owner.id, scope)
    with h.as_(admin):
        h.iam.attach_policy("builtin.member", bob.id, scope)
        with pytest.raises(PermissionDeniedError):
            h.iam.attach_policy("builtin.owner", bob.id, scope)
        with pytest.raises(PermissionDeniedError):
            h.iam.detach_policy("builtin.owner", owner.id, scope)
        # Admins cannot reach another workspace's roles at all.
        with pytest.raises(IAMNotFoundError):
            h.iam.attach_policy("builtin.member", bob.id, "abi:org-1:ws-2")
    with h.as_(owner):
        h.iam.attach_policy("builtin.owner", bob.id, scope)
        assert h.iam.detach_policy("builtin.owner", bob.id, scope) is True


def test_workspace_roles_keep_the_platform_companion_in_step(h):
    bob = h.user()

    def companions():
        return {
            a.policy_id
            for a in h.iam.store.list_attachments(principal_id=bob.id)
            if a.policy_id.startswith("builtin.platform.")
        }

    h.attach("builtin.viewer", bob.id, "abi:org-1:-")
    assert companions() == set()
    h.attach("builtin.viewer", bob.id, "abi:org-1:ws-1")
    assert companions() == {"builtin.platform.viewer"}
    assert h.allowed("triple_store:QueryView", "abi:-:-:triple_store:view/v", bob)
    h.attach("builtin.member", bob.id, "abi:org-1:ws-2")
    assert companions() == {"builtin.platform.member"}
    h.admin("detach_policy", "builtin.member", bob.id, "abi:org-1:ws-2")
    assert companions() == {"builtin.platform.viewer"}
    h.admin("detach_policy", "builtin.viewer", bob.id, "abi:org-1:ws-1")
    assert companions() == set()


def test_every_user_holds_self(h):
    bob = h.user()
    assert h.allowed("iam:GetPrincipal", f"abi:-:-:iam:principal/{bob.id}", bob)
    assert h.allowed("activity_log:Query", f"abi:-:-:activity_log:actor/{bob.id}", bob)
    assert not h.allowed("iam:GetPrincipal", "abi:-:-:iam:principal/usr_other", bob)
    ci = h.service_account("ci/x")
    assert not h.allowed("iam:GetPrincipal", f"abi:-:-:iam:principal/{ci.id}", ci)


# -- transitional bootstrap ---------------------------------------------------------------------------------------


def test_engine_and_api_hold_a_transitional_broad_policy(h):
    for actor in ("engine", "api"):
        with h.as_(actor=actor):
            explanation = h.iam.authorizer.explain(
                h.context(actor=actor), "triple_store:DropGraph", graph("a")
            )
        assert explanation.allowed
        assert explanation.statement is not None
        assert explanation.statement.sid == "TransitionalBroadAccess"
        assert explanation.statement.policy_id == f"builtin.{actor}"


def test_idp_holds_only_its_own_namespace_secrets_and_sender(h):
    assert h.allowed(
        "document:Put", "abi:-:-:document:document/idp/users/u1", actor="idp"
    )
    assert h.allowed("secret:Get", "abi:-:-:secret:secret/idp%2Fkey", actor="idp")
    assert h.allowed("email:Send", "abi:-:-:email:sender/default", actor="idp")
    assert not h.allowed(
        "document:Get", "abi:-:-:document:document/other/c/1", actor="idp"
    )
    assert not h.allowed(QUERY, graph("a"), actor="idp")


def test_an_unknown_remote_module_holds_the_transitional_module_policy(h):
    module = "people"
    own = f"abi:-:-:document:collection/{module}/contacts"
    assert h.allowed("document:Find", own, actor=module)
    assert not h.allowed(
        "document:Find", "abi:-:-:document:collection/other/c", actor=module
    )
    assert h.allowed(
        "dataset:Query", f"abi:-:-:dataset:dataset/{module}/orders", actor=module
    )
    assert h.allowed(QUERY, graph("a"), actor=module)
    assert not h.allowed("iam:CreatePolicy", "abi:-:-:iam:policy/p", actor=module)
    # A module named with slashes is one encoded segment.
    assert h.allowed(
        "document:Get",
        "abi:-:-:document:document/module%2Facme%2Fpeople/c/1",
        actor="module/acme/people",
    )
    # Once IAM knows the account, it holds what is attached to it, nothing more.
    h.service_account(module)
    assert not h.allowed("document:Find", own, actor=module)


# -- the opt-out ----------------------------------------------------------------------------------------------------


def test_allow_all_allows_everything_and_says_so(caplog):
    from naas_abi_core import logger

    messages: list[str] = []
    sink = logger.add(lambda m: messages.append(str(m)), level="WARNING")
    try:
        service = IAMService(IAMStoreMemory(), lambda _source: AllowAllAuthorizer())
    finally:
        logger.remove(sink)
    assert any("allow_all" in m for m in messages)
    with use_call_context(ANONYMOUS):
        assert service.authorize("triple_store:DropGraph", graph("a")).allowed
        assert service.filter(QUERY, [graph("a"), graph("b")]).allowed == [
            graph("a"),
            graph("b"),
        ]
        service.require("anything:Goes", "*")
