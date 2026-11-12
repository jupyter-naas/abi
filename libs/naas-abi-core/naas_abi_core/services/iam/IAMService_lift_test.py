"""Removing a restriction, and granting below a container, follow what the actor holds.

* A detach of a customer policy holding a Deny is decided like an attach of it,
  and the principal it restricts (itself, or through a group) never lifts it,
  unless it may attach it unscoped.
* "Grant only what you hold": a ``${scope}`` held below a container counts for
  the container types under it only, never for another type of the same action.
"""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import module_scopes, roles
from naas_abi_core.services.iam.IAMPorts import (
    GrantNotHeldError,
    IAMNotFoundError,
    PermissionDeniedError,
)
from naas_abi_core.services.iam.tests.iam_harness import (
    below,
    document,
    graph,
    name_in,
    org,
    statement,
    workspace,
)

DROP = "triple_store:DropGraph"
LEDGER = graph("https%3A%2F%2Fexample.org%2Fledger")


@pytest.fixture
def restricted(h, iam):
    """An org admin, a ws-1 admin and a ws-1 member; the org admin's Deny
    policy, owned by the org."""
    ws1 = h.register("ws-1", "org-1")
    org_admin, ws_admin, member = h.user("org-admin"), h.user("ws-admin"), h.user("m")
    h.attach(roles.ADMIN, org_admin.id, below("org-1"))
    h.attach(roles.ADMIN, ws_admin.id, ws1)
    h.attach(roles.MEMBER, member.id, ws1)
    with h.as_(org_admin):
        deny = iam.create_policy(
            "No dropping graphs",
            document(statement("Deny", [DROP], ["${scope}/triple_store:graph/*"])),
            scope=org("org-1"),
        )
    return ws1, org_admin, ws_admin, member, deny


def test_detach_keeps_a_deny_on_whom_it_restricts(h, iam, restricted):
    ws1, org_admin, ws_admin, _member, deny = restricted
    with h.as_(org_admin):
        iam.attach_policy(deny.id, ws_admin.id, workspace("ws-1", "org-1"))
    assert not h.allowed(DROP, LEDGER, ws_admin)
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.detach_policy(deny.id, ws_admin.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    # Whoever imposed it lifts it.
    with h.as_(org_admin):
        assert iam.detach_policy(deny.id, ws_admin.id, ws1)
    assert h.allowed(DROP, LEDGER, ws_admin)


def test_detach_keeps_a_deny_on_a_group_its_restricted_member_is_in(h, iam, restricted):
    ws1, org_admin, ws_admin, _member, deny = restricted
    with as_service_account("engine"):
        team = iam.create_group("ws-1 admins", scope=ws1)
        iam.add_group_member(team.id, ws_admin.id)
    with h.as_(org_admin):
        iam.attach_policy(deny.id, team.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError):
        iam.detach_policy(deny.id, team.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)


def test_leaving_a_group_keeps_its_deny_on_whom_it_restricts(h, iam, restricted):
    ws1, org_admin, ws_admin, _member, deny = restricted
    with as_service_account("engine"):
        team = iam.create_group("ws-1 admins", scope=ws1)
        iam.add_group_member(team.id, ws_admin.id)
    with h.as_(org_admin):
        iam.attach_policy(deny.id, team.id, ws1)
    with h.as_(ws_admin):
        with pytest.raises(PermissionDeniedError):
            iam.remove_group_member(team.id, ws_admin.id)
        with pytest.raises(PermissionDeniedError):
            iam.delete_group(team.id)
    assert ws_admin.id in iam.store.list_group_members(team.id)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    # Whoever imposed it may let the member go.
    with h.as_(org_admin):
        assert iam.remove_group_member(team.id, ws_admin.id)
    assert h.allowed(DROP, LEDGER, ws_admin)


def test_editing_a_deny_keeps_it_on_whom_it_restricts(h, iam, restricted):
    ws1, org_admin, ws_admin, _member, _deny = restricted
    with h.as_(org_admin):
        local = iam.create_policy(
            "No dropping graphs here",
            document(statement("Deny", [DROP], ["${scope}/triple_store:graph/*"])),
            scope=ws1,
        )
        iam.attach_policy(local.id, ws_admin.id, ws1)
    elsewhere = document(
        statement("Deny", [DROP], ["${scope}/triple_store:graph/another"])
    )
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.update_policy(local.id, expected_revision=1, document=elsewhere)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    # Renaming it lifts nothing; whoever imposed it may still change it.
    with h.as_(ws_admin):
        iam.update_policy(local.id, expected_revision=1, name="renamed")
    with h.as_(org_admin):
        iam.update_policy(local.id, expected_revision=2, document=elsewhere)
    assert h.allowed(DROP, LEDGER, ws_admin)


@pytest.fixture
def derived(h, iam, restricted):
    """A Deny that reaches the ws-1 admin through a parent: the org admin's
    ``Parent`` (Allow and Deny of dropping graphs, Allow of reading them), and
    ``Sub`` derived from it at ws-1 (reading only), attached to the ws-1 admin."""
    ws1, org_admin, ws_admin, _member, _deny = restricted
    query = "triple_store:Query"
    with h.as_(org_admin):
        parent = iam.create_policy(
            "Parent",
            document(
                statement("Allow", [DROP, query], ["${scope}/triple_store:graph/*"]),
                statement("Deny", [DROP], ["${scope}/triple_store:graph/*"]),
            ),
            scope=org("org-1"),
        )
        iam.attach_policy(parent.id, org_admin.id, org("org-1"))
        sub = iam.create_policy(
            "Sub",
            document(statement("Allow", [query], ["${scope}/triple_store:graph/*"])),
            scope=ws1,
            parent=parent.id,
        )
        iam.attach_policy(sub.id, ws_admin.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    return ws1, org_admin, ws_admin, sub


def test_detach_keeps_a_parents_deny_on_whom_it_restricts(h, iam, derived):
    ws1, org_admin, ws_admin, sub = derived
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.detach_policy(sub.id, ws_admin.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    with h.as_(org_admin):
        assert iam.detach_policy(sub.id, ws_admin.id, ws1)
    assert h.allowed(DROP, LEDGER, ws_admin)


def test_reparenting_keeps_a_parents_deny_on_whom_it_restricts(h, iam, derived):
    _ws1, org_admin, ws_admin, sub = derived
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.update_policy(sub.id, expected_revision=1, parent="")
    assert not h.allowed(DROP, LEDGER, ws_admin)
    # Whoever imposed it may still take the sub-policy out of its chain.
    with h.as_(org_admin):
        iam.update_policy(sub.id, expected_revision=1, parent="")
    assert h.allowed(DROP, LEDGER, ws_admin)


QUERY = "triple_store:Query"
DROPPING = document(
    statement("Allow", [DROP, QUERY], ["${scope}/triple_store:graph/*"]),
    statement("Deny", [DROP], ["${scope}/triple_store:graph/*"]),
)
READING = document(statement("Allow", [QUERY], ["${scope}/triple_store:graph/*"]))


def _derive(iam, name: str, owner: str, parent_id: str, doc=READING):
    return iam.create_policy(name, doc, scope=owner, parent=parent_id)


def test_editing_a_parent_keeps_its_deny_on_whom_its_sub_policies_restrict(
    h, iam, restricted
):
    """A parent's Denies reach whoever holds a policy below it: one of them
    may not edit the parent to drop them, even where it may edit the parent."""
    ws1, org_admin, ws_admin, _member, _deny = restricted
    with h.as_(org_admin):
        parent = iam.create_policy("Parent", DROPPING, scope=ws1)
        iam.attach_policy(parent.id, org_admin.id, ws1)
        sub = _derive(iam, "Sub", ws1, parent.id)
        iam.attach_policy(sub.id, org_admin.id, ws1)
        below = _derive(iam, "Below", ws1, sub.id)
        iam.attach_policy(below.id, ws_admin.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.update_policy(parent.id, expected_revision=1, document=READING)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    # The org admin holds it too, so it is restricted as well; IAM's own writes
    # still change it.
    with h.as_(org_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.update_policy(parent.id, expected_revision=1, document=READING)
    with as_service_account("engine"):
        iam.update_policy(parent.id, expected_revision=1, document=READING)
    assert h.allowed(DROP, LEDGER, ws_admin)


def test_reparenting_a_parent_keeps_its_chains_deny_on_whom_it_restricts(
    h, iam, restricted
):
    ws1, org_admin, ws_admin, _member, _deny = restricted
    with h.as_(org_admin):
        grand = iam.create_policy("Grand", DROPPING, scope=ws1)
        iam.attach_policy(grand.id, org_admin.id, ws1)
        parent = _derive(iam, "Parent", ws1, grand.id)
        iam.attach_policy(parent.id, org_admin.id, ws1)
        sub = _derive(iam, "Sub", ws1, parent.id)
        iam.attach_policy(sub.id, ws_admin.id, ws1)
    assert not h.allowed(DROP, LEDGER, ws_admin)
    with h.as_(ws_admin), pytest.raises(PermissionDeniedError, match="restricts you"):
        iam.update_policy(parent.id, expected_revision=1, parent="")
    assert not h.allowed(DROP, LEDGER, ws_admin)


def test_detach_of_a_deny_from_another_member_is_decided_like_its_attach(
    h, iam, restricted
):
    ws1, _org_admin, ws_admin, member, deny = restricted
    # The ws-1 admin may attach it to a member there, and so remove it.
    with h.as_(ws_admin):
        iam.attach_policy(deny.id, member.id, ws1)
        assert iam.detach_policy(deny.id, member.id, ws1)
    # A member may attach nothing, and removes nothing.
    with h.as_(ws_admin):
        iam.attach_policy(deny.id, member.id, ws1)
    with h.as_(member), pytest.raises((PermissionDeniedError, IAMNotFoundError)):
        iam.detach_policy(deny.id, member.id, ws1)


def test_detach_of_a_role_one_holds_stays_open(h, iam, restricted):
    """A built-in role's own Denies leave with its Allows: leaving it widens nothing."""
    ws1, _org_admin, ws_admin, _member, _deny = restricted
    with h.as_(ws_admin):
        assert iam.detach_policy(roles.ADMIN, ws_admin.id, ws1)


EXPORT = "acme_crm:Export"


def _crm(iam) -> None:
    iam._register_catalog(
        module_scopes.module_catalog(
            {
                "version": 1,
                "resource_types": [
                    {"name": "project", "container": True},
                    {"name": "report", "id": "opaque"},
                ],
                "actions": [
                    {
                        "name": "CreateProject",
                        "level": "write",
                        "resource_types": ["project"],
                        "creates": True,
                    },
                    {
                        "name": "Export",
                        "level": "read",
                        "resource_types": ["project", "report"],
                    },
                ],
            },
            "acme.crm",
        )
    )


def test_grant_keeps_a_scope_held_below_a_container_to_its_container_types(h, iam):
    _crm(iam)
    ws1 = h.register("ws-1", "org-1")
    giver, taker = h.user("giver"), h.user("taker")
    h.attach(roles.ADMIN, giver.id, ws1)
    h.attach(roles.MEMBER, taker.id, ws1)
    with as_service_account("engine"):
        projects = iam.create_policy(
            "Export projects",
            document(statement("Allow", [EXPORT], ["${scope}"])),
            scope=org("org-1"),
        )
        iam.attach_policy(projects.id, giver.id, below("org-1"))
    report = name_in(ws1, "acme_crm:report/q3")
    assert not h.allowed(EXPORT, report, giver)
    with h.as_(giver), pytest.raises(GrantNotHeldError):
        reports = iam.create_policy(
            "Reports",
            document(statement("Allow", [EXPORT], ["${scope}/acme_crm:report/*"])),
            scope=ws1,
        )
        iam.attach_policy(reports.id, taker.id, ws1)
    assert not h.allowed(EXPORT, report, taker)
    # For an action on container types only, it still counts: each container
    # under the org.
    create = "acme_crm:CreateProject"
    with as_service_account("engine"):
        creating = iam.create_policy(
            "Create projects",
            document(statement("Allow", [create], ["${scope}"])),
            scope=org("org-1"),
        )
        iam.attach_policy(creating.id, giver.id, below("org-1"))
    with h.as_(giver):
        given = iam.create_policy(
            "Projects",
            document(statement("Allow", [create], ["${scope}/acme_crm:project/*"])),
            scope=ws1,
        )
        iam.attach_policy(given.id, taker.id, ws1)
    assert h.allowed(create, name_in(ws1, "acme_crm:project/p1"), taker)
