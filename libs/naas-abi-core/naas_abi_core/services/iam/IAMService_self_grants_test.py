"""Self grants (``set_self_grants``): what every user holds beyond the catalogs'
``self_`` rows, set by the deployment (Nexus's personal workspaces). They live in
the stored ``builtin.self``, so a regeneration by any IAM instance keeps them."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import as_service_account
from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.IAMService import IAMService
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness

CATALOG = ActionCatalog(
    service="nexus",
    version=1,
    resource_types=(
        ResourceType("workspace", container=True, platform_companions=True),
    ),
    actions=(ActionSpec("CreateWorkspace", "admin", ("workspace",), creates=True),),
)
PERSONAL = "abi:nexus:workspace/ws-1"
GRANT = roles.SelfGrant("nexus:CreateWorkspace", ("abi:nexus:workspace/*",))


@pytest.fixture
def h(iam) -> IAMHarness:
    with as_service_account("engine"):
        iam.register_catalog(CATALOG)
    return IAMHarness(iam)


def _creates(h: IAMHarness, user) -> bool:
    return h.allowed("nexus:CreateWorkspace", PERSONAL, actor="api", on_behalf_of=user)


def test_every_user_holds_a_self_grant_until_it_is_withdrawn(h):
    bob = h.user()
    assert not _creates(h, bob)
    with as_service_account("engine"):
        h.iam.set_self_grants([GRANT])
    assert _creates(h, bob)
    with as_service_account("engine"):
        h.iam.set_self_grants([])
    assert not _creates(h, bob)


def test_self_grants_survive_a_regeneration_by_another_instance(h):
    with as_service_account("engine"):
        h.iam.set_self_grants([GRANT])
    other = IAMService(h.iam.store)
    other.bootstrap()
    with as_service_account("engine"):
        other.register_catalog(
            ActionCatalog(
                service="nexus",
                version=2,
                resource_types=CATALOG.resource_types,
                actions=(
                    *CATALOG.actions,
                    ActionSpec("GetWorkspace", "read", ("workspace",)),
                ),
            )
        )
    statements = h.iam.store.get_policy(roles.SELF).document.statements
    assert any("nexus:CreateWorkspace" in s.actions for s in statements)


def test_setting_self_grants_needs_the_catalogs_registration(h):
    bob = h.user()
    with (
        h.as_(actor="api", on_behalf_of=bob),
        pytest.raises((PermissionDeniedError, ResourceNotFoundError)),
    ):
        h.iam.set_self_grants([GRANT])
