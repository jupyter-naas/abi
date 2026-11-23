"""Platform grants (``set_platform_grants``) live in the stored platform
policies, so a regeneration of the managed policies by any IAM instance keeps
them."""

from __future__ import annotations

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import ActionSpec
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.names import resource_name
from naas_abi_core.services.iam.tests.iam_harness import TRIPLE_STORE

SHARED = resource_name("triple_store", "graph", "shared")
READ_ONLY = resource_name("triple_store", "graph", "readonly")


def _statements(iam: IAMService, policy_id: str):
    return iam.store.get_policy(policy_id).document.statements


def _actions_on(iam: IAMService, policy_id: str, resource: str) -> set[str]:
    return {
        action
        for statement in _statements(iam, policy_id)
        if resource in statement.resources
        for action in statement.actions
    }


def _set_grants(iam: IAMService) -> None:
    with as_service_account("engine"):
        iam.set_platform_grants(
            [
                roles.PlatformGrant("triple_store", (SHARED,)),
                roles.PlatformGrant("triple_store", (READ_ONLY,), member_writes=False),
            ]
        )


def test_the_grants_are_in_the_platform_policies(iam):
    _set_grants(iam)

    assert "triple_store:Query" in _actions_on(iam, roles.PLATFORM_VIEWER, SHARED)
    assert "triple_store:Insert" not in _actions_on(iam, roles.PLATFORM_VIEWER, SHARED)
    assert "triple_store:Insert" in _actions_on(iam, roles.PLATFORM_MEMBER, SHARED)
    assert "triple_store:Insert" not in _actions_on(
        iam, roles.PLATFORM_MEMBER, READ_ONLY
    )
    assert "triple_store:Query" in _actions_on(iam, roles.PLATFORM_MEMBER, READ_ONLY)


def test_platform_grants_survive_a_regeneration_by_another_instance(iam):
    """Another process (a module approval, the engine's boot) regenerates the
    managed policies from its own registry, knowing nothing of the grants it did
    not set: they stay, rebuilt against the catalog it registers."""
    _set_grants(iam)

    other = IAMService(iam.store)
    other.bootstrap()
    changed = TRIPLE_STORE.__class__(
        service="triple_store",
        version=2,
        resource_types=TRIPLE_STORE.resource_types,
        actions=(*TRIPLE_STORE.actions, ActionSpec("CountTriples", "read", ("graph",))),
    )
    with as_service_account("engine"):
        other.register_catalog(changed)

    for policy_id in (roles.PLATFORM_VIEWER, roles.PLATFORM_MEMBER):
        for resource in (SHARED, READ_ONLY):
            assert {"triple_store:Query", "triple_store:CountTriples"} <= _actions_on(
                iam, policy_id, resource
            )
    # The levels are kept too: the read-only grant gives members no write.
    assert "triple_store:Insert" in _actions_on(iam, roles.PLATFORM_MEMBER, SHARED)
    assert "triple_store:Insert" not in _actions_on(
        iam, roles.PLATFORM_MEMBER, READ_ONLY
    )

    # A further regeneration changes nothing.
    before = {p.id: p.document for p in iam._all_policies()}
    other._refresh_builtin_policies()
    assert {p.id: p.document for p in iam._all_policies()} == before


def test_set_platform_grants_replaces_the_set(iam):
    _set_grants(iam)
    with as_service_account("engine"):
        iam.set_platform_grants([roles.PlatformGrant("triple_store", (SHARED,))])

    assert _actions_on(iam, roles.PLATFORM_VIEWER, READ_ONLY) == set()
    assert "triple_store:Query" in _actions_on(iam, roles.PLATFORM_VIEWER, SHARED)
