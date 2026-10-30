"""An IAM store of an earlier schema version upgrades: what the SQLite and
PostgreSQL tests run on a store they downgrade by hand."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from unittest.mock import patch

from naas_abi_core.services.iam.adapters.secondary import iam_sql
from naas_abi_core.services.iam.adapters.secondary.iam_sql import (
    SCHEMA_VERSION,
    IAMStoreSQL,
)
from naas_abi_core.services.iam.IAMPorts import (
    Attachment,
    GroupMapping,
    LegacyScopeSet,
    PendingGrant,
    Placement,
    Policy,
    PrincipalRecord,
    new_id,
)
from naas_abi_core.services.iam.names import PLATFORM, UNRESOLVED, resource_name
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    WS,
    _Rewriter,
    group,
    policy,
)

# What version 1 had: no owner scopes, no sets, no parents and no containers
# (version 2 had no sets, version 3 no parents, version 4 still its sets,
# version 5 no containers). The store of today makes no ``iam_scope_sets``:
# versions 3 and 4 get theirs back.
SETS_TABLE = (
    "CREATE TABLE {schema}iam_scope_sets (org VARCHAR(64) NOT NULL, "
    "workspace VARCHAR(64) NOT NULL, modules TEXT, features TEXT, "
    "PRIMARY KEY (org, workspace))"
)
NO_CONTAINERS = (
    "DROP TABLE {schema}iam_containers",
    "ALTER TABLE {schema}iam_placements DROP COLUMN container",
)
DOWNGRADE_TO_5 = (*NO_CONTAINERS, "UPDATE {schema}iam_state SET schema_version = 5")
DOWNGRADE_TO_4 = (
    *NO_CONTAINERS,
    SETS_TABLE,
    "UPDATE {schema}iam_state SET schema_version = 4",
)
DOWNGRADE_TO_3 = (
    *NO_CONTAINERS,
    "DROP INDEX {schema}iam_policies_parent",
    "ALTER TABLE {schema}iam_policies DROP COLUMN parent_id",
    SETS_TABLE,
    "UPDATE {schema}iam_state SET schema_version = 3",
)
DOWNGRADE = (
    *DOWNGRADE_TO_3[:4],
    "ALTER TABLE {schema}iam_policies DROP COLUMN owner_scope",
    "ALTER TABLE {schema}iam_principals DROP COLUMN owner_scope",
    "UPDATE {schema}iam_state SET schema_version = 1",
)
DOWNGRADE_TO_2 = (
    *DOWNGRADE_TO_3[:4],
    "UPDATE {schema}iam_state SET schema_version = 2",
)


def check_upgrade(
    open_store: Callable[[], IAMStoreSQL], execute: Callable[[str], None]
) -> None:
    store = open_store()
    shared = store.create_policy(policy())
    hand_made = store.create_principal(group("sales"))
    bound = store.create_principal(
        PrincipalRecord(id=new_id("grp"), kind="group", name="idp:acme:Sales")
    )
    store.map_idp_group(GroupMapping("acme", "Sales", bound.id))
    store.attach(Attachment(new_id("att"), shared.id, bound.id, "abi:org-1:ws-1"))
    store.attach(Attachment(new_id("att"), shared.id, bound.id, "abi:org-1:*"))
    # Bound in org-1 first, then in org-2 and unscoped: one group held them all.
    everywhere = store.create_principal(
        PrincipalRecord(id=new_id("grp"), kind="group", name="idp:acme:Ops")
    )
    store.map_idp_group(GroupMapping("acme", "Ops", everywhere.id))
    for scope in ("abi:org-1:ws-1", "abi:org-2:ws-9", None):
        store.attach(Attachment(new_id("att"), shared.id, everywhere.id, scope))
    old_platform = store.create_policy(
        Policy(
            id=new_id("pol"),
            name="policy editor",
            document=PolicyDocument(
                statements=(
                    Statement("Allow", ("iam:GetPolicy",), ("abi:-:-:iam:policy/*",)),
                    Statement("Allow", ("iam:GetGroup",), ("${scope}:iam:group/*",)),
                    Statement("Deny", ("*",), ("*",)),
                )
            ),
        )
    )
    unbound = store.create_principal(
        PrincipalRecord(id=new_id("grp"), kind="group", name="idp:acme:All")
    )
    store.map_idp_group(GroupMapping("acme", "All", unbound.id))
    store.close()
    for statement in DOWNGRADE:
        execute(statement)
    # Version 1 kept the org a group was made for; the store of today writes
    # none (the column stays, read by this upgrade only).
    for made_in_org in (hand_made, bound, everywhere):
        execute(
            "UPDATE {schema}iam_principals SET org = 'org-1' "  # nosec B608
            f"WHERE id = '{made_in_org.id}'"
        )

    with patch.object(iam_sql, "logger") as log:
        upgraded = open_store()
    # A stored policy that named the platform's policies or groups as abi:-:-
    # is reported; `*` still reaches them, so it is not.
    warned = [str(c.args[0]) for c in log.warning.call_args_list]
    assert len(warned) == 1 and old_platform.id in warned[0]
    assert "abi:-:-:iam:policy/*" in warned[0]
    assert "${scope}:iam:group/*" in warned[0] and "'*'" not in warned[0]
    try:
        assert upgraded.get_policy(shared.id).owner_scope == PLATFORM
        assert upgraded.get_principal(hand_made.id).owner_scope == PLATFORM
        # A group an IdP binding made belongs to the org it was made for, in
        # the grammar of then until the names are rewritten.
        assert upgraded.get_principal(bound.id).owner_scope == "abi:org-1:-"
        assert upgraded.get_principal(unbound.id).owner_scope == PLATFORM
        # Held at org-2 and unscoped too: org-1's admins must not own it.
        assert upgraded.get_principal(everywhere.id).owner_scope == PLATFORM
        assert upgraded.create_policy(policy()).owner_scope == PLATFORM
    finally:
        upgraded.close()
    # Opening it again changes nothing.
    again = open_store()
    try:
        assert again.get_principal(bound.id).owner_scope == "abi:org-1:-"
        assert SCHEMA_VERSION == 6
        assert again.legacy_scope_sets() == []
    finally:
        again.close()


def check_upgrade_from_3(
    open_store: Callable[[], IAMStoreSQL], execute: Callable[[str], None]
) -> None:
    """A store of version 3 (no parents) opens with every policy at the top of
    its own tree, and records parents from then on."""
    store = open_store()
    kept = store.create_policy(policy())
    store.close()
    for statement in DOWNGRADE_TO_3:
        execute(statement)
    upgraded = open_store()
    try:
        assert upgraded.get_policy(kept.id).parent_id is None
        child = upgraded.create_policy(replace(policy(), parent_id=kept.id))
        assert [p.id for p in upgraded.list_sub_policies(kept.id)] == [child.id]
    finally:
        upgraded.close()
    # Opening it again changes nothing.
    again = open_store()
    try:
        assert again.get_policy(child.id).parent_id == kept.id
    finally:
        again.close()


def check_upgrade_from_2(
    open_store: Callable[[], IAMStoreSQL], execute: Callable[[str], None]
) -> None:
    """A store of version 2 (no sets) opens with no legacy set to move."""
    store = open_store()
    kept = store.create_policy(policy())
    store.close()
    for statement in DOWNGRADE_TO_2:
        execute(statement)
    upgraded = open_store()
    try:
        assert upgraded.get_policy(kept.id).id == kept.id
        assert upgraded.legacy_scope_sets() == []
        assert upgraded.drop_legacy_scope_sets() is False
    finally:
        upgraded.close()


def check_upgrade_from_4(
    open_store: Callable[[], IAMStoreSQL], execute: Callable[[str], None]
) -> None:
    """A store of version 4 keeps its sets, unread, until they are moved:
    ``legacy_scope_sets`` reads them as stored, ``drop_legacy_scope_sets``
    drops the table. ``iam:GetSet`` and ``iam:PutSet`` leave the customer
    policies that named them, a statement naming nothing else with them."""
    store = open_store()
    named = store.create_policy(
        Policy(
            id=new_id("pol"),
            name="set reader",
            document=PolicyDocument(
                statements=(
                    Statement("Allow", ("iam:GetSet",), ("${scope}:iam:set/*",)),
                    Statement(
                        "Allow",
                        ("iam:PutSet", "iam:GetPolicy"),
                        ("${scope}:iam:*",),
                        sid="Both",
                    ),
                )
            ),
        )
    )
    untouched = store.create_policy(policy())
    store.close()
    for statement in DOWNGRADE_TO_4:
        execute(statement)
    execute(
        "INSERT INTO {schema}iam_scope_sets (org, workspace, modules, features) "
        """VALUES ('org-1', '-', '["acme.people"]', NULL)"""
    )
    execute(
        "INSERT INTO {schema}iam_scope_sets (org, workspace, modules, features) "
        """VALUES ('org-1', 'ws-1', '[]', '["chat"]')"""
    )
    upgraded = open_store()
    try:
        assert upgraded.legacy_scope_sets() == [
            LegacyScopeSet("org-1", "-", ("acme.people",), None),
            LegacyScopeSet("org-1", "ws-1", (), ("chat",)),
        ]
        rewritten = upgraded.get_policy(named.id)
        assert rewritten.document.statements == (
            Statement("Allow", ("iam:GetPolicy",), ("${scope}:iam:*",), sid="Both"),
        )
        assert rewritten.revision == named.revision + 1
        assert upgraded.get_policy(untouched.id).revision == untouched.revision
    finally:
        upgraded.close()
    # Opening it again changes nothing; dropping them is once.
    again = open_store()
    try:
        assert again.get_policy(named.id).revision == named.revision + 1
        assert len(again.legacy_scope_sets()) == 2
        before = again.revision()
        assert again.drop_legacy_scope_sets() is True
        assert again.revision() > before
        assert again.legacy_scope_sets() == []
        assert again.drop_legacy_scope_sets() is False
    finally:
        again.close()


def check_upgrade_from_5(
    open_store: Callable[[], IAMStoreSQL], execute: Callable[[str], None]
) -> None:
    """A store of version 5 (names ``abi:<org>:<ws>:...``) narrows, never widens,
    until its names are rewritten: a placement of the old form reads as
    ``names.UNRESOLVED``, the platform's (``-``, ``-``) as the platform, and the
    old platform ``abi:-:-`` as an owner or a scope is the platform ``abi:``."""
    store = open_store()
    platform_policy = store.create_policy(replace(policy(), owner_scope="abi:-:-"))
    workspace_policy = store.create_policy(
        replace(policy(), owner_scope="abi:org-1:ws-1")
    )
    platform_group = store.create_principal(replace(group(), owner_scope="abi:-:-"))
    store.attach(
        Attachment(new_id("att"), platform_policy.id, platform_group.id, "abi:-:-")
    )
    store.attach(
        Attachment(
            new_id("att"), platform_policy.id, platform_group.id, "abi:org-1:ws-1"
        )
    )
    invited = store.add_pending_grant(
        PendingGrant(
            new_id("pgr"), "builtin", "bob@example.com", platform_policy.id, "abi:-:-"
        )
    )
    store.close()
    for statement in DOWNGRADE_TO_5:
        execute(statement)
    for id_key, org, workspace in (
        ("nexus-ws-1", "org-1", "ws-1"),
        ("nexus-ws-1/*", "org-1", "ws-1"),
        ("module", "-", "-"),
        # A workspace deleted since: Nexus names no container for it.
        ("nexus-ws-gone", "org-1", "ws-gone"),
    ):
        execute(
            "INSERT INTO {schema}iam_placements (service, id_key, org, workspace) "  # nosec B608
            f"VALUES ('document', '{id_key}', '{org}', '{workspace}')"
        )
    upgraded = open_store()
    try:
        assert upgraded.list_placements() == [
            Placement("document", "module", PLATFORM),
            Placement("document", "nexus-ws-1", UNRESOLVED),
            Placement("document", "nexus-ws-1/*", UNRESOLVED),
            Placement("document", "nexus-ws-gone", UNRESOLVED),
        ]
        assert upgraded.list_containers() == []
        assert upgraded.get_policy(platform_policy.id).owner_scope == PLATFORM
        assert upgraded.get_policy(workspace_policy.id).owner_scope == "abi:org-1:ws-1"
        assert upgraded.get_principal(platform_group.id).owner_scope == PLATFORM
        assert {
            a.scope for a in upgraded.list_attachments(principal_id=platform_group.id)
        } == {PLATFORM, "abi:org-1:ws-1"}
        grant = upgraded.get_pending_grant(invited.id)
        assert grant is not None and grant.scope == PLATFORM
        # The rewrite of the names, once Nexus registers its containers.
        counts = upgraded.rewrite_names(_Rewriter())
        assert (counts["containers"], counts["placements"]) == (2, 2)
        assert counts["policies"] == 1 and counts["attachments"] == 1
        assert upgraded.list_placements() == [
            Placement("document", "module", PLATFORM),
            Placement("document", "nexus-ws-1", WS),
            Placement("document", "nexus-ws-1/*", WS),
            # Kept in the old form: it reads as UNRESOLVED, a name it can make.
            Placement("document", "nexus-ws-gone", UNRESOLVED),
        ]
        resource_name("document", "namespace", "nexus-ws-gone", container=UNRESOLVED)
        assert upgraded.get_policy(workspace_policy.id).owner_scope == WS
    finally:
        upgraded.close()
    # Opening it again changes nothing, and the rewrite is done.
    again = open_store()
    try:
        assert again.list_placements()[1] == Placement("document", "nexus-ws-1", WS)
        assert set(again.rewrite_names(_Rewriter()).values()) == {0}
        assert SCHEMA_VERSION == 6
    finally:
        again.close()
