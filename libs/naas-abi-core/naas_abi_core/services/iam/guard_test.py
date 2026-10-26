"""ServiceGuard: names placed by IAM, the create rule, placements."""

from __future__ import annotations

import pytest

from naas_abi_core.engine.call_context import (
    CallContext,
    Principal,
    use_call_context,
)
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.guard import (
    ServiceGuard,
    authorization_error_code,
    raise_authorization_error,
)
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.tests.iam_harness import statement

BOXES = ActionCatalog(
    service="boxes",
    version=1,
    resource_types=(
        ResourceType("box", id="opaque", container=True),
        ResourceType("item", id="path"),
        ResourceType("label", id="opaque", placement="platform"),
    ),
    actions=(
        ActionSpec("ListBoxes", "list", ("box",)),
        ActionSpec("GetBox", "read", ("box",)),
        ActionSpec("CreateBox", "write", ("box",), creates=True),
        ActionSpec("PutItem", "write", ("item",), creates=True),
        ActionSpec("UseLabel", "read", ("label",)),
    ),
)


class BoxNotFound(LookupError):
    pass


@pytest.fixture
def guard(iam, h) -> ServiceGuard:
    iam._register_catalog(BOXES)
    h.first_party_may("boxes")
    return ServiceGuard(BOXES, lambda: iam)


@pytest.fixture
def bob(h):
    bob = h.user()
    h.grant(bob.id, statement("Allow", ["boxes:*"], ["*"]))
    return bob


def _as(record, workspace_id: str | None = None):
    return use_call_context(
        CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            on_behalf_of=Principal(id=record.id, kind="user"),
            workspace_id=workspace_id,
        )
    )


def test_an_unwired_guard_checks_nothing():
    guard = ServiceGuard(BOXES, lambda: None)
    assert guard.require("GetBox", "box", "b") is None
    assert guard.filter("ListBoxes", "box", ["a", "b"], lambda b: b) == ["a", "b"]


def test_names_are_placed_by_iam(h, guard):
    h.admin("put_placement", "boxes", "b", "org-1", "ws-1")
    assert guard.name("box", "b") == "abi:org-1:ws-1:boxes:box/b"
    assert guard.name("label", "x") == "abi:-:-:boxes:label/x"


def test_an_invisible_resource_gets_the_services_not_found(h, guard):
    with h.as_(h.user()), pytest.raises(BoxNotFound):
        guard.require("GetBox", "box", "b", not_found=lambda: BoxNotFound("b"))


def test_a_new_container_is_placed_in_the_target_workspace(h, guard, bob):
    h.admin("put_scope", "org-1", "ws-1")
    with _as(bob, "ws-1"):
        creation = guard.create("CreateBox", "box", "b")
    assert creation.name == "abi:org-1:ws-1:boxes:box/b"
    creation.record()
    assert h.iam.resolve_placement("boxes", "b") == ("org-1", "ws-1")
    assert h.iam.resolve_placement("boxes", "b/inside") == ("org-1", "ws-1")
    guard.forget("box", "b")
    assert h.iam.placement_of("boxes", "b") is None
    assert h.iam.placement_of("boxes", "b/inside") is None


def test_a_child_takes_its_containers_placement(h, guard, bob):
    h.admin("put_scope", "org-1", "ws-1")
    h.admin("put_placement", "boxes", "b", "org-1", "ws-1")
    h.admin("put_placement", "boxes", "b/*", "org-1", "ws-1")
    with _as(bob, "ws-1"):
        creation = guard.create("PutItem", "item", ["b", "i"])
    assert creation.name == "abi:org-1:ws-1:boxes:item/b/i"
    assert not (creation.record_exact or creation.record_prefix)


def test_a_child_cannot_be_claimed_from_another_workspace(h, guard, bob):
    h.admin("put_scope", "org-1", "ws-1")
    h.admin("put_scope", "org-1", "ws-2")
    h.admin("put_placement", "boxes", "b/*", "org-1", "ws-1")
    with _as(bob, "ws-2"), pytest.raises(PermissionDeniedError):
        guard.create("PutItem", "item", ["b", "i"])


def test_a_mismatch_is_not_found_for_a_caller_who_cannot_see_it(h, guard):
    h.admin("put_scope", "org-1", "ws-2")
    h.admin("put_placement", "boxes", "b/*", "org-1", "ws-1")
    carol = h.user("carol")
    h.grant(carol.id, statement("Allow", ["boxes:*"], ["abi:org-1:ws-2:*"]))
    with _as(carol, "ws-2"), pytest.raises(BoxNotFound):
        guard.create("PutItem", "item", ["b", "i"], not_found=lambda: BoxNotFound("b"))


def test_an_unknown_target_workspace_places_on_the_platform(h, guard, bob):
    """A workspace IAM has no scope for places the resource on the platform."""
    with _as(bob, "ws-unregistered"):
        creation = guard.create("CreateBox", "box", "b")
    assert creation.name == "abi:-:-:boxes:box/b"
    creation.record()
    assert h.iam.placement_of("boxes", "b") is not None
    assert h.iam.resolve_placement("boxes", "b") == ("-", "-")


def test_the_create_action_is_checked_on_the_name_as_placed(h, guard):
    h.admin("put_scope", "org-1", "ws-1")
    dave = h.user("dave")
    h.grant(dave.id, statement("Allow", ["boxes:*"], ["abi:org-1:ws-2:*"]))
    with _as(dave, "ws-1"), pytest.raises(ResourceNotFoundError):
        guard.create("CreateBox", "box", "b")


def test_wire_codes_round_trip():
    for error in (PermissionDeniedError("a", "r"), ResourceNotFoundError("r")):
        code = authorization_error_code(error)
        assert code is not None
        with pytest.raises(type(error)):
            raise_authorization_error(code, str(error))
    assert authorization_error_code(ValueError()) is None
    raise_authorization_error("SOMETHING_ELSE", "x")  # not ours: returns
