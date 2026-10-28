"""Sub-policies, in process: the shared scenarios (``tests/sub_policy_contract.py``),
the parent's variables, chains IAM cannot read whole, and the cache."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.IAMPorts import IIAMService
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests import sub_policy_contract as contract
from naas_abi_core.services.iam.tests.iam_harness import (
    IAMHarness,
    document,
    graph,
    statement,
)

QUERY = "triple_store:Query"
WS1 = "abi:org-1:ws-1"


def _as_user(h: IAMHarness):
    @contextmanager
    def as_user(record) -> Iterator[IIAMService]:
        with h.as_(record):
            yield h.iam

    return as_user


@pytest.mark.parametrize("scenario", contract.SCENARIOS, ids=lambda s: s.__name__)
def test_sub_policy_scenarios_in_process(h, scenario):
    scenario(h.iam, _as_user(h))


def _scopes(h: IAMHarness) -> None:
    h.admin("put_scope", "org-1")
    h.admin("put_scope", "org-1", "ws-1")
    h.admin("put_scope", "org-1", "ws-2")


def test_the_parents_variables_come_from_the_sub_policys_attachment(h):
    """${scope} is the sub-policy's attachment scope; ${principal.id} the member
    evaluated, through a group too."""
    _scopes(h)
    parent = h.admin(
        "create_policy",
        "own graphs",
        document(
            statement("Allow", [QUERY], ["${scope}:triple_store:graph/${principal.id}"])
        ),
    )
    child = h.admin(
        "create_policy",
        "graphs",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
        scope=WS1,
        parent=parent.id,
    )
    bob, alice = h.user("bob"), h.user("alice")
    team = h.group("team")
    for member in (bob, alice):
        h.admin("add_group_member", team.id, member.id)
    h.attach(child.id, team.id, WS1)
    assert h.allowed(QUERY, graph(bob.id), bob)
    assert not h.allowed(QUERY, graph(alice.id), bob)
    assert h.allowed(QUERY, graph(alice.id), alice)
    assert not h.allowed(QUERY, graph(bob.id, workspace="ws-2"), bob)


def test_a_parent_allow_beyond_scope_bounds_a_scoped_sub_policy(h):
    """A parent's Allows are bounds: one written for every org still bounds a
    workspace's sub-policy attached at its scope."""
    _scopes(h)
    parent = h.admin(
        "create_policy",
        "sales anywhere",
        document(statement("Allow", [QUERY], ["abi:*:*:triple_store:graph/sales"])),
    )
    child = h.admin(
        "create_policy",
        "ws graphs",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
        scope=WS1,
        parent=parent.id,
    )
    bob = h.user()
    h.attach(child.id, bob.id, WS1)
    assert h.allowed(QUERY, graph("sales"), bob)
    assert not h.allowed(QUERY, graph("hr"), bob)
    assert not h.allowed(QUERY, graph("sales", workspace="ws-2"), bob)


def test_a_sub_policy_whose_chain_uses_scope_is_attached_at_a_scope(h):
    _scopes(h)
    parent = h.admin(
        "create_policy",
        "ws graphs",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
    )
    child = h.admin(
        "create_policy",
        "every graph",
        document(statement("Allow", [QUERY], ["abi:*:*:triple_store:graph/*"])),
        parent=parent.id,
    )
    with pytest.raises(ValueError, match="scope"):
        h.attach(child.id, h.user().id)


def test_a_parent_deny_beyond_scope_is_attached_at_a_scope_by_the_platform_admin(h):
    """The chain's Deny is the sub-policy's: as for a platform policy denying
    beyond ``${scope}:``, a scope's admin does not impose it."""
    _scopes(h)
    parent = h.admin(
        "create_policy",
        "no hr anywhere",
        document(
            statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"]),
            statement("Deny", [QUERY], ["abi:*:*:triple_store:graph/hr"]),
        ),
    )
    child = h.admin(
        "create_policy",
        "ws graphs",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
        scope=WS1,
        parent=parent.id,
    )
    admin, bob = h.user("admin"), h.user("bob")
    h.attach(roles.ADMIN, admin.id, WS1)
    with h.as_(admin), pytest.raises(PermissionError, match="unscoped"):
        h.iam.attach_policy(child.id, bob.id, WS1)
    root = h.user("root")
    h.attach(roles.PLATFORM_ADMIN, root.id)
    with h.as_(root):
        h.iam.attach_policy(child.id, bob.id, WS1)
    assert not h.allowed(QUERY, graph("hr"), bob)
    assert h.allowed(QUERY, graph("sales"), bob)


def test_a_chain_iam_cannot_read_whole_grants_nothing(h):
    """A parent gone or a cycle written under IAM (two concurrent writes): the
    sub-policy's Allows count for nothing, its Denies still refuse."""
    _scopes(h)
    parent = h.admin(
        "create_policy",
        "graphs",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
    )
    child = h.admin(
        "create_policy",
        "ws graphs",
        document(
            statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"]),
            statement(
                "Deny", ["triple_store:Insert"], ["${scope}:triple_store:graph/*"]
            ),
        ),
        scope=WS1,
        parent=parent.id,
    )
    bob = h.user()
    h.attach(child.id, bob.id, WS1)
    h.grant(bob.id, statement("Allow", ["triple_store:Insert"], ["*"]))
    assert h.allowed(QUERY, graph("sales"), bob)
    store = h.iam.store
    # A cycle: the parent under its own sub-policy, written to the store directly.
    store.update_policy(replace(parent, parent_id=child.id), parent.revision)
    h.iam.invalidate()
    assert not h.allowed(QUERY, graph("sales"), bob)
    assert not h.allowed("triple_store:Insert", graph("sales"), bob)


def test_a_narrowed_parent_reaches_another_process_on_its_change_event(h):
    """Another IAMService on the same store (another engine, ``abi iam``) holds
    the subject in its cache until it hears the change."""
    _scopes(h)
    parent = h.admin(
        "create_policy",
        "a and b",
        document(
            statement(
                "Allow", [QUERY], [graph("a").replace("abi:org-1:ws-1", "${scope}")]
            ),
            statement(
                "Allow", [QUERY], [graph("b").replace("abi:org-1:ws-1", "${scope}")]
            ),
        ),
    )
    child = h.admin(
        "create_policy",
        "ws graphs",
        document(statement("Allow", [QUERY], ["${scope}:triple_store:graph/*"])),
        scope=WS1,
        parent=parent.id,
    )
    bob = h.user()
    h.attach(child.id, bob.id, WS1)
    other = IAMService(h.iam.store)
    other._register_catalog(h.iam.catalogs.get("triple_store"))  # type: ignore[arg-type]
    with h.as_(bob):
        assert other.authorize(QUERY, graph("b")).allowed
    h.admin(
        "update_policy",
        parent.id,
        expected_revision=1,
        document=document(
            statement(
                "Allow", [QUERY], [graph("a").replace("abi:org-1:ws-1", "${scope}")]
            )
        ),
    )
    assert h.allowed(QUERY, graph("a"), bob) and not h.allowed(QUERY, graph("b"), bob)
    with h.as_(bob):
        assert other.authorize(QUERY, graph("b")).allowed  # cached, not told yet
        assert other.refresh_if_changed()
        assert not other.authorize(QUERY, graph("b")).allowed
        assert other.authorize(QUERY, graph("a")).allowed


def test_a_module_variable_of_a_parent_is_bound_for_the_module(h):
    """A parent's ``${module.id}`` is bound for a module's account as its own."""
    with as_service_account("engine"):
        parent = h.iam.create_policy(
            "own namespace",
            document(
                statement(
                    "Allow", [QUERY], ["abi:-:-:triple_store:graph/${module.id}-*"]
                )
            ),
        )
        child = h.iam.create_policy(
            "graphs",
            document(statement("Allow", [QUERY], ["abi:-:-:triple_store:graph/*"])),
            parent=parent.id,
        )
    account = h.service_account("module/acme/people")
    h.attach(child.id, account.id)
    platform = "abi:-:-:triple_store:graph/"
    assert h.allowed(QUERY, platform + "people-x", account)
    assert not h.allowed(QUERY, platform + "crm-x", account)
