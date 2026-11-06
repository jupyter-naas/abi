"""Viewing as a principal, in process: the shared scenarios
(``tests/view_as_contract.py``), the catalog, the roles' statements and the names.

A decision on a view runs in the engine that holds IAM, like ``link_user``: no
NATS endpoint and no SDK operation.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import replace

import pytest

from naas_abi_core.services.iam import roles
from naas_abi_core.services.iam.catalog import CatalogRegistry
from naas_abi_core.services.iam.iam_catalog import CATALOG as IAM
from naas_abi_core.services.iam.IAMPorts import (
    IIAMService,
    PermissionDeniedError,
    ViewAsRefused,
)
from naas_abi_core.services.iam.IAMService import IAMService, view_as_resource
from naas_abi_core.services.iam.names import parse_resource_name
from naas_abi_core.services.iam.tests import view_as_contract as contract
from naas_abi_core.services.iam.tests.iam_harness import IAMHarness


def _as_user(h: IAMHarness):
    @contextmanager
    def as_user(record) -> Iterator[IAMService]:
        with h.as_(record):
            yield h.iam

    return as_user


@pytest.mark.parametrize("scenario", contract.SCENARIOS, ids=lambda s: s.__name__)
def test_view_as_scenarios_in_process(h, scenario):
    scenario(h.iam, _as_user(h))


# -- the catalog ----------------------------------------------------------------------


def test_the_catalog_declares_the_type_and_the_action():
    view_as = IAM.resource_type("view_as")
    assert view_as is not None
    assert view_as.placement == "placed" and view_as.id == "opaque"
    assert not view_as.container and not view_as.policy_only
    action = IAM.action("ViewAs")
    assert action is not None
    assert action.level == "admin"
    assert action.resource_types == ("view_as",)
    assert not action.creates and not action.owner_only
    # In process only, like link_user: nothing is served for it.
    assert action.subjects == ()


def test_the_name_is_the_principal_in_the_container():
    name = view_as_resource("usr_01abc", contract.ALPHA)
    assert name == f"{contract.ALPHA}/iam:view_as/usr_01abc"
    parsed = parse_resource_name(name)
    assert (parsed.service, parsed.type) == ("iam", "view_as")
    assert view_as_resource("usr_01abc", "abi:") == "abi:iam:view_as/usr_01abc"


def test_a_decision_on_a_view_is_not_an_operation_of_the_port():
    """Not on NATS, not in the SDK: neither side of the wire names it."""
    import inspect

    from naas_abi_core.services.iam.adapters.primary import (
        iam__primary_adapter__NATS as primary,
    )
    from naas_abi_core.services.iam.adapters.secondary import (
        IAMSecondaryAdapterNATSClient as client,
    )

    for module in (primary, client):
        assert "view_as" not in inspect.getsource(module)
    with pytest.raises(NotImplementedError):
        IIAMService.view_as_verdict(None, "usr_x", contract.ALPHA)  # type: ignore[arg-type]


def test_view_as_refused_is_a_permission_denied_error():
    assert issubclass(ViewAsRefused, PermissionDeniedError)


# -- the roles' statements ---------------------------------------------------------------


def _registry(*, with_view_as: bool) -> CatalogRegistry:
    iam = IAM
    if not with_view_as:
        iam = replace(
            IAM,
            resource_types=tuple(t for t in IAM.resource_types if t.name != "view_as"),
            actions=tuple(a for a in IAM.actions if a.name != "ViewAs"),
        )
    registry = CatalogRegistry()
    registry.register(iam)
    registry.register(contract.NEXUS)
    return registry


@pytest.mark.parametrize("role", [roles.ADMIN, roles.OWNER])
def test_admin_and_owner_hold_view_as_in_one_statement_of_its_own(role):
    new = roles.role_policy(role, _registry(with_view_as=True)).document.statements
    old = roles.role_policy(role, _registry(with_view_as=False)).document.statements
    added = [s for s in new if s not in old]
    assert len(added) == 1
    assert added[0].effect == "Allow"
    assert added[0].actions == ("iam:ViewAs",)
    assert added[0].resources == ("${scope}/iam:view_as/*",)
    # Every other statement, as it was.
    assert [s for s in new if s not in added] == list(old)


@pytest.mark.parametrize("role", [roles.VIEWER, roles.MEMBER])
def test_viewer_and_member_hold_none_of_it(role):
    policy = roles.role_policy(role, _registry(with_view_as=True))
    assert "iam:ViewAs" not in {
        a for s in policy.document.statements for a in s.actions
    }
    assert roles.role_policy(role, _registry(with_view_as=True)) == roles.role_policy(
        role, _registry(with_view_as=False)
    )


def test_the_platform_admin_holds_it_through_the_wildcard():
    policy = next(
        p
        for p in roles.builtin_policies(_registry(with_view_as=True))
        if p.id == roles.PLATFORM_ADMIN
    )
    assert any(
        s.actions == ("*",) and s.resources == ("*",)
        for s in policy.document.statements
    )


def test_api_may_ask_on_behalf_of_the_viewer(h):
    api = roles.api_policy(_registry(with_view_as=True))
    assert "iam:ViewAs" in {a for s in api.document.statements for a in s.actions}
