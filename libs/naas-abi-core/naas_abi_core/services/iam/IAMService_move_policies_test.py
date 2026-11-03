"""Moving policies to another owner (``move_policies``), and what the editor of a
sub-policy is offered within a parent they may not read (``grantable``)."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes
from naas_abi_core.services.iam.IAMPorts import (
    IAMConflictError,
    IAMNotFoundError,
    PermissionDeniedError,
)
from naas_abi_core.services.iam.tests.iam_harness import (
    IAMHarness,
    document,
    org,
    statement,
    workspace,
)

USE = "module:UseAgent"
ORG = org("org-1")
WS1 = workspace("ws-1")
WS2 = workspace("ws-2")


def _agents(*names: str) -> list[str]:
    return [f"${{scope}}/module:agent/people/{name}" for name in names]


def _agent(name: str, where: str = WS1) -> str:
    return f"{where}/module:agent/people/{name}"


def _tree(h: IAMHarness):
    """The org's access (platform), a workspace's access owned by the org (as the
    sets' move made it), and a sub-policy of it owned by the org, attached at ws-1."""
    h.iam._register_catalog(module_scopes.CATALOG)
    h.register("ws-1")
    h.register("ws-2")
    org_access = h.admin(
        "create_policy",
        "Acme access",
        document(statement("Allow", [USE], _agents("*"))),
    )
    ws_access = h.admin(
        "create_policy",
        "Alpha access",
        document(statement("Allow", [USE], _agents("a", "b"))),
        scope=ORG,
        parent=org_access.id,
    )
    admins = h.admin(
        "create_policy",
        "Alpha modules (admins and owners)",
        document(statement("Allow", [USE], _agents("*"))),
        scope=ORG,
        parent=ws_access.id,
    )
    return org_access, ws_access, admins


def test_policies_move_to_the_workspace_with_their_attachments(h):
    _org_access, ws_access, admins = _tree(h)
    bob = h.user("bob")
    h.attach(admins.id, bob.id, WS1)
    before = [h.allowed(USE, _agent(name), bob) for name in ("a", "b", "c")]
    with as_service_account("api"):
        moved = h.iam.move_policies({ws_access.id: WS1, admins.id: WS1})
    assert [p.owner_scope for p in moved] == [WS1, WS1]
    # No decision reads an owner.
    assert (
        [h.allowed(USE, _agent(name), bob) for name in ("a", "b", "c")]
        == before
        == [
            True,
            True,
            False,
        ]
    )
    assert h.admin("get_policy", admins.id).parent_id == ws_access.id


def test_a_sub_policy_left_outside_its_parents_new_owner_is_refused(h):
    _org_access, ws_access, admins = _tree(h)
    with as_service_account("api"), pytest.raises(ValueError, match=admins.id):
        h.iam.move_policies({ws_access.id: WS1})
    assert h.admin("get_policy", ws_access.id).owner_scope == ORG


def test_an_owner_outside_the_parents_is_refused(h):
    _org_access, ws_access, admins = _tree(h)
    # Below its parent's owner: fine.
    with as_service_account("api"):
        h.iam.move_policies({admins.id: WS1})
    with as_service_account("api"), pytest.raises(ValueError, match=admins.id):
        # Above its parent's new owner.
        h.iam.move_policies({ws_access.id: WS1, admins.id: ORG})
    with as_service_account("api"), pytest.raises(ValueError):
        # Two workspaces: the sub-policy is not within its parent's.
        h.iam.move_policies({ws_access.id: WS1, admins.id: WS2})


def test_an_attachment_beyond_the_new_owner_is_refused(h):
    _org_access, ws_access, admins = _tree(h)
    h.attach(admins.id, h.user("bob").id, WS2)
    with as_service_account("api"), pytest.raises(ValueError, match=WS2):
        h.iam.move_policies({ws_access.id: WS1, admins.id: WS1})
    assert h.admin("get_policy", admins.id).owner_scope == ORG


def test_a_document_not_written_for_the_new_owner_is_refused(h):
    h.iam._register_catalog(module_scopes.CATALOG)
    h.register("ws-1")
    anywhere = h.admin(
        "create_policy", "every agent", document(statement("Allow", [USE], ["abi:*"]))
    )
    with as_service_account("api"), pytest.raises(ValueError):
        h.iam.move_policies({anywhere.id: WS1})


def test_a_managed_policy_never_moves(h):
    h.register("ws-1")
    with as_service_account("api"), pytest.raises(IAMConflictError):
        h.iam.move_policies({"builtin.member": WS1})


def test_moving_needs_update_where_it_is_and_create_where_it_goes(h):
    _org_access, ws_access, admins = _tree(h)
    bob = h.user("bob")
    # Bob administers the org's own policies, not ws-1's: he may not move one there.
    h.grant(
        bob.id,
        statement(
            "Allow",
            ["iam:CreatePolicy", "iam:UpdatePolicy", "iam:GetPolicy"],
            ["${scope}/iam:policy/*"],
        ),
        scope=ORG,
    )
    with h.as_(bob), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        h.iam.move_policies({ws_access.id: WS1, admins.id: WS1})
    assert h.admin("get_policy", ws_access.id).owner_scope == ORG


def test_the_editor_of_a_sub_policy_is_offered_what_they_hold_within_its_parent(h):
    """A workspace admin edits their workspace's access (owned there) within its
    organisation's, which they may neither read nor derive from: ``grantable``
    answers with what they hold, met with the chain."""
    org_access, ws_access, admins = _tree(h)
    with as_service_account("api"):
        h.iam.move_policies({ws_access.id: WS1, admins.id: WS1})
    carol = h.user("carol")
    h.grant(
        carol.id,
        statement(
            "Allow", ["iam:UpdatePolicy", "iam:GetPolicy"], ["${scope}/iam:policy/*"]
        ),
        scope=WS1,
    )
    h.attach(ws_access.id, carol.id, WS1)
    with h.as_(carol):
        offered = h.iam.grantable(WS1, parent=org_access.id)
        agents = {
            pattern
            for catalog in offered
            for action in catalog.actions
            if action.action == USE
            for pattern in action.resources
        }
        assert agents == {
            "${scope}/module:agent/people/a",
            "${scope}/module:agent/people/b",
        }
        # Not at another workspace, where she edits nothing under it.
        with pytest.raises(PermissionDeniedError):
            h.iam.grantable(WS2, parent=org_access.id)
    # Someone who may not update it learns nothing of the parent.
    dave = h.user("dave")
    h.attach(ws_access.id, dave.id, WS1)
    with h.as_(dave), pytest.raises(PermissionDeniedError):
        h.iam.grantable(WS1, parent=org_access.id)
