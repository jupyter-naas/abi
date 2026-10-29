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
from naas_abi_core.services.iam.names import PLATFORM, UNRESOLVED
from naas_abi_core.services.iam.tests.iam_harness import statement, workspace

WS1 = workspace("ws-1")
WS2 = workspace("ws-2")

BOXES = ActionCatalog(
    service="boxes",
    version=1,
    resource_types=(
        ResourceType("box", id="opaque", id_prefix=True),
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


def _as(record, container: str | None = None):
    return use_call_context(
        CallContext(
            principal=Principal(id="api", kind="service_account", name="api"),
            on_behalf_of=Principal(id=record.id, kind="user"),
            container=container,
        )
    )


def test_an_unwired_guard_checks_nothing():
    guard = ServiceGuard(BOXES, lambda: None)
    assert guard.require("GetBox", "box", "b") is None
    assert guard.filter("ListBoxes", "box", ["a", "b"], lambda b: b) == ["a", "b"]


def test_names_are_placed_by_iam(h, guard):
    h.register("ws-1")
    h.admin("put_placement", "boxes", "b", WS1)
    assert guard.name("box", "b") == f"{WS1}/boxes:box/b"
    assert guard.name("label", "x") == "abi:boxes:label/x"


def test_an_invisible_resource_gets_the_services_not_found(h, guard):
    with h.as_(h.user()), pytest.raises(BoxNotFound):
        guard.require("GetBox", "box", "b", not_found=lambda: BoxNotFound("b"))


def test_a_new_id_prefix_is_placed_in_the_container_of_the_call(h, guard, bob):
    h.register("ws-1")
    with _as(bob, WS1):
        creation = guard.create("CreateBox", "box", "b")
    assert creation.name == f"{WS1}/boxes:box/b"
    creation.record()
    assert h.iam.resolve_placement("boxes", "b") == WS1
    assert h.iam.resolve_placement("boxes", "b/inside") == WS1
    guard.forget("box", "b")
    assert h.iam.placement_of("boxes", "b") is None
    assert h.iam.placement_of("boxes", "b/inside") is None


def test_a_child_takes_its_id_prefixs_placement(h, guard, bob):
    h.register("ws-1")
    h.admin("put_placement", "boxes", "b", WS1)
    h.admin("put_placement", "boxes", "b/*", WS1)
    with _as(bob, WS1):
        creation = guard.create("PutItem", "item", ["b", "i"])
    assert creation.name == f"{WS1}/boxes:item/b/i"
    assert not (creation.record_exact or creation.record_prefix)


def test_a_child_cannot_be_claimed_from_another_container(h, guard, bob):
    h.register("ws-1")
    h.register("ws-2")
    h.admin("put_placement", "boxes", "b/*", WS1)
    with _as(bob, WS2), pytest.raises(PermissionDeniedError):
        guard.create("PutItem", "item", ["b", "i"])


def test_a_mismatch_is_not_found_for_a_caller_who_cannot_see_it(h, guard):
    h.register("ws-1")
    h.register("ws-2")
    h.admin("put_placement", "boxes", "b/*", WS1)
    carol = h.user("carol")
    h.grant(carol.id, statement("Allow", ["boxes:*"], [f"{WS2}/*"]))
    with _as(carol, WS2), pytest.raises(BoxNotFound):
        guard.create("PutItem", "item", ["b", "i"], not_found=lambda: BoxNotFound("b"))


def test_an_unknown_container_places_nothing(h, guard, bob):
    """A container IAM does not know (or names under another path): the create
    is not found, whoever asks (bob holds everything), and nothing is placed."""
    h.register("ws-1")
    for claimed in (workspace("ws-unregistered"), workspace("ws-1", "org-2")):
        with _as(bob, claimed):
            assert h.iam.call_container() == UNRESOLVED
            with pytest.raises(BoxNotFound):
                guard.create(
                    "CreateBox", "box", "b", not_found=lambda: BoxNotFound("b")
                )
    assert h.iam.placement_of("boxes", "b") is None


def test_an_unknown_container_is_denied_to_a_role_at_a_container(h, guard):
    """Not found, and the same create in a container it knows is placed there."""
    h.register("ws-1")
    carol = h.user("carol")
    h.grant(carol.id, statement("Allow", ["boxes:*"], [f"{WS1}/*"]))
    with _as(carol, workspace("ws-unregistered")), pytest.raises(BoxNotFound):
        guard.create("CreateBox", "box", "b", not_found=lambda: BoxNotFound("b"))
    with _as(carol, WS1):
        assert guard.create("CreateBox", "box", "b").name == f"{WS1}/boxes:box/b"


def test_a_covering_placement_refuses_another_container(h, guard, bob):
    """An existing placement keeps the name where it is, whatever the call
    names: a top-level placed resource of ws-1 is not re-created in ws-2."""
    h.register("ws-1")
    h.register("ws-2")
    h.admin("put_placement", "boxes", "b", WS1)
    with _as(bob, WS2), pytest.raises(PermissionDeniedError):
        guard.create("CreateBox", "box", "b")
    with _as(bob, WS1):
        assert guard.create("CreateBox", "box", "b").name == f"{WS1}/boxes:box/b"
    with _as(bob):
        assert guard.create("CreateBox", "box", "b").name == f"{WS1}/boxes:box/b"


def test_a_platform_placement_refuses_any_container(h, guard, bob):
    h.register("ws-1")
    h.admin("put_placement", "boxes", "b/*", PLATFORM)
    with _as(bob, WS1), pytest.raises(PermissionDeniedError):
        guard.create("PutItem", "item", ["b", "i"])
    with _as(bob):
        assert guard.create("PutItem", "item", ["b", "i"]).name == (
            "abi:boxes:item/b/i"
        )


def test_the_create_action_is_checked_on_the_name_as_placed(h, guard):
    h.register("ws-1")
    h.register("ws-2")
    dave = h.user("dave")
    h.grant(dave.id, statement("Allow", ["boxes:*"], [f"{WS2}/*"]))
    with _as(dave, WS1), pytest.raises(ResourceNotFoundError):
        guard.create("CreateBox", "box", "b")


def test_wire_codes_round_trip():
    for error in (PermissionDeniedError("a", "r"), ResourceNotFoundError("r")):
        code = authorization_error_code(error)
        assert code is not None
        with pytest.raises(type(error)):
            raise_authorization_error(code, str(error))
    assert authorization_error_code(ValueError()) is None
    raise_authorization_error("SOMETHING_ELSE", "x")  # not ours: returns
