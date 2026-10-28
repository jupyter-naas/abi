"""An IAM store of schema version 1 upgrades: what the SQLite and PostgreSQL
tests run on a store they downgrade by hand."""

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
    Policy,
    PrincipalRecord,
    ScopeSet,
    new_id,
)
from naas_abi_core.services.iam.policy import PolicyDocument, Statement
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    group,
    policy,
)

# What version 1 had: no owner scopes, no sets and no parents (version 2 had no
# sets, version 3 no parents).
DOWNGRADE_TO_3 = (
    "DROP INDEX {schema}iam_policies_parent",
    "ALTER TABLE {schema}iam_policies DROP COLUMN parent_id",
    "UPDATE {schema}iam_state SET schema_version = 3",
)
DOWNGRADE = (
    *DOWNGRADE_TO_3[:2],
    "ALTER TABLE {schema}iam_policies DROP COLUMN owner_scope",
    "ALTER TABLE {schema}iam_principals DROP COLUMN owner_scope",
    "DROP TABLE {schema}iam_scope_sets",
    "UPDATE {schema}iam_state SET schema_version = 1",
)
DOWNGRADE_TO_2 = (
    *DOWNGRADE_TO_3[:2],
    "DROP TABLE {schema}iam_scope_sets",
    "UPDATE {schema}iam_state SET schema_version = 2",
)


def check_upgrade(
    open_store: Callable[[], IAMStoreSQL], execute: Callable[[str], None]
) -> None:
    store = open_store()
    shared = store.create_policy(policy())
    hand_made = store.create_principal(group("sales", org="org-1"))
    bound = store.create_principal(
        PrincipalRecord(
            id=new_id("grp"), kind="group", name="idp:acme:Sales", org="org-1"
        )
    )
    store.map_idp_group(GroupMapping("acme", "Sales", bound.id))
    store.attach(Attachment(new_id("att"), shared.id, bound.id, "abi:org-1:ws-1"))
    store.attach(Attachment(new_id("att"), shared.id, bound.id, "abi:org-1:*"))
    # Bound in org-1 first, then in org-2 and unscoped: one group held them all.
    everywhere = store.create_principal(
        PrincipalRecord(
            id=new_id("grp"), kind="group", name="idp:acme:Ops", org="org-1"
        )
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
        PrincipalRecord(id=new_id("grp"), kind="group", name="idp:acme:All", org=None)
    )
    store.map_idp_group(GroupMapping("acme", "All", unbound.id))
    store.close()
    for statement in DOWNGRADE:
        execute(statement)

    with patch.object(iam_sql, "logger") as log:
        upgraded = open_store()
    # A stored policy that named the platform's policies or groups as abi:-:-
    # is reported; `*` still reaches them, so it is not.
    warned = [str(c.args[0]) for c in log.warning.call_args_list]
    assert len(warned) == 1 and old_platform.id in warned[0]
    assert "abi:-:-:iam:policy/*" in warned[0]
    assert "${scope}:iam:group/*" in warned[0] and "'*'" not in warned[0]
    try:
        assert upgraded.get_policy(shared.id).owner_scope == "abi:-:-"
        assert upgraded.get_principal(hand_made.id).owner_scope == "abi:-:-"
        # A group an IdP binding made belongs to the org it was made for.
        assert upgraded.get_principal(bound.id).owner_scope == "abi:org-1:-"
        assert upgraded.get_principal(unbound.id).owner_scope == "abi:-:-"
        # Held at org-2 and unscoped too: org-1's admins must not own it.
        assert upgraded.get_principal(everywhere.id).owner_scope == "abi:-:-"
        assert upgraded.create_policy(policy()).owner_scope == "abi:-:-"
    finally:
        upgraded.close()
    # Opening it again changes nothing.
    again = open_store()
    try:
        assert again.get_principal(bound.id).owner_scope == "abi:org-1:-"
        assert SCHEMA_VERSION == 4
        again.put_scope_set(ScopeSet("org-1", modules=("acme.people",)))
        assert again.list_scope_sets() == [ScopeSet("org-1", modules=("acme.people",))]
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
    """A store of version 2 (no sets) opens with every org and workspace's set
    unrecorded, everything, and records sets from then on."""
    store = open_store()
    kept = store.create_policy(policy())
    store.close()
    for statement in DOWNGRADE_TO_2:
        execute(statement)
    upgraded = open_store()
    try:
        assert upgraded.get_policy(kept.id).id == kept.id
        assert upgraded.list_scope_sets() == []
        workspace = ScopeSet("org-1", "ws-1", modules=(), features=("chat",))
        upgraded.put_scope_set(workspace)
        assert upgraded.list_scope_sets() == [workspace]
    finally:
        upgraded.close()
