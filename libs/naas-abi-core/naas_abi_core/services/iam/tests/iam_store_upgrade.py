"""An IAM store of schema version 1 upgrades: what the SQLite and PostgreSQL
tests run on a store they downgrade by hand."""

from __future__ import annotations

from collections.abc import Callable

from naas_abi_core.services.iam.adapters.secondary.iam_sql import (
    SCHEMA_VERSION,
    IAMStoreSQL,
)
from naas_abi_core.services.iam.IAMPorts import GroupMapping, PrincipalRecord, new_id
from naas_abi_core.services.iam.tests.iam__secondary_adapter__generic_test import (
    group,
    policy,
)

# What version 1 had: no owner scopes.
DOWNGRADE = (
    "ALTER TABLE {schema}iam_policies DROP COLUMN owner_scope",
    "ALTER TABLE {schema}iam_principals DROP COLUMN owner_scope",
    "UPDATE {schema}iam_state SET schema_version = 1",
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
    unbound = store.create_principal(
        PrincipalRecord(id=new_id("grp"), kind="group", name="idp:acme:All", org=None)
    )
    store.map_idp_group(GroupMapping("acme", "All", unbound.id))
    store.close()
    for statement in DOWNGRADE:
        execute(statement)

    upgraded = open_store()
    try:
        assert upgraded.get_policy(shared.id).owner_scope == "abi:-:-"
        assert upgraded.get_principal(hand_made.id).owner_scope == "abi:-:-"
        # A group an IdP binding made belongs to the org it was made for.
        assert upgraded.get_principal(bound.id).owner_scope == "abi:org-1:-"
        assert upgraded.get_principal(unbound.id).owner_scope == "abi:-:-"
        assert upgraded.create_policy(policy()).owner_scope == "abi:-:-"
    finally:
        upgraded.close()
    # Opening it again changes nothing.
    again = open_store()
    try:
        assert again.get_principal(bound.id).owner_scope == "abi:org-1:-"
        assert SCHEMA_VERSION == 2
    finally:
        again.close()
