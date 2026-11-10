"""ResourceGuard: names, checks, list push-down and placements on create."""

from __future__ import annotations

import io
from contextlib import contextmanager
from dataclasses import replace

import pytest

from naas_abi_core.engine.call_context import (
    current_call_context,
    service_account,
    use_call_context,
)
from naas_abi_core.services.iam.catalog import ActionCatalog, ActionSpec, ResourceType
from naas_abi_core.services.iam.enforcement import (
    ResourceGuard,
    internal_call,
    own_storage,
    scan_allowed,
)
from naas_abi_core.services.iam.IAMPorts import (
    PermissionDeniedError,
    ResourceNotFoundError,
)
from naas_abi_core.services.iam.names import PLATFORM
from naas_abi_core.services.iam.tests.iam_harness import statement, workspace

WS1 = workspace("ws-1")
WS2 = workspace("ws-2")

STORE = ActionCatalog(
    service="store",
    version=1,
    resource_types=(
        ResourceType("namespace", id="path", id_prefix=True),
        ResourceType("item", id="path"),
        ResourceType("key", id="opaque"),
    ),
    actions=(
        ActionSpec("ListKeys", "list", ("key",)),
        ActionSpec("Get", "read", ("key", "item")),
        ActionSpec("Create", "write", ("item",), creates=True),
        ActionSpec("Drop", "admin", ("namespace",)),
    ),
)


@pytest.fixture
def guard(iam, h):
    with internal_call():
        iam.register_catalog(STORE)
    h.first_party_may("store")
    return ResourceGuard(STORE, lambda: iam)


def _in(container: str | None):
    return use_call_context(replace(current_call_context(), container=container))


def test_without_iam_nothing_is_checked():
    guard = ResourceGuard(STORE, lambda: None)
    guard.require("Get", "key", "anything")
    assert guard.filter("Get", "key", ["a", "b"], lambda k: k) == ["a", "b"]
    # A list in every case, whatever iterable the caller handed over.
    listed = guard.filter("Get", "key", (k for k in ("a", "b")), lambda k: k)
    assert isinstance(listed, list) and listed == ["a", "b"]
    assert isinstance(guard.filter("Get", "key", ("a",), lambda k: k), list)
    assert (
        guard.create("Create", "item", ["ns", "x"], prefix=("namespace", ["ns"]))()
        is None
    )


def test_names_are_placed_by_iam(iam, h, guard):
    h.register("ws-1")
    assert guard.name("key", "a/b") == "abi:store:key/a%2Fb"
    with internal_call():
        iam.put_placement("store", "team%3A*", WS1)
    assert guard.name("key", "team:x") == f"{WS1}/store:key/team%3Ax"


def test_require_answers_not_found_or_denied(h, guard):
    bob = h.user("bob")
    h.grant(bob.id, statement("Allow", ["store:ListKeys"], ["abi:store:key/seen*"]))
    with h.as_(bob):
        with pytest.raises(PermissionDeniedError):
            guard.require("Get", "key", "seen")  # visible: it may list it
        with pytest.raises(KeyError):
            guard.require("Get", "key", "other", not_found=lambda: KeyError("other"))
        with pytest.raises(ResourceNotFoundError):
            guard.require("Get", "key", "other")


def test_id_prefixes_push_the_callers_allows_down(h, guard):
    bob = h.user("bob")
    h.grant(
        bob.id,
        statement(
            "Allow",
            ["store:ListKeys"],
            ["abi:store:key/team%3A*", "abi:store:key/team%3Aa%2F*"],
        ),
    )
    with h.as_(bob):
        assert guard.id_prefixes("ListKeys", "key") == ["team:"]
    with h.as_(h.user("nobody")):
        assert guard.id_prefixes("ListKeys", "key") == []
    with internal_call():
        assert guard.id_prefixes("ListKeys", "key") is None  # everything: no narrowing


def test_scan_pages_after_filtering_within_the_pushed_down_prefixes(h, guard):
    bob = h.user("bob")
    h.grant(
        bob.id,
        statement("Allow", ["store:ListKeys"], ["abi:store:key/b*"]),
        statement("Deny", ["store:ListKeys"], ["abi:store:key/b2"]),
    )
    keys = ["a1", "b1", "b2", "b3", "b4", "c1"]
    scanned: list[str] = []

    def fetch(prefix, limit, after):
        scanned.append(prefix)
        matching = [
            k for k in keys if k.startswith(prefix) and (after is None or k > after)
        ]
        page = matching[:limit]
        return page, (page[-1] if len(matching) > limit else None)

    with h.as_(bob):
        first = scan_allowed(guard, "ListKeys", "key", "", 2, None, fetch)
        assert first == (["b1", "b3"], "b3")
        assert set(scanned) == {"b"}  # never a, never c
        assert scan_allowed(guard, "ListKeys", "key", "", 2, "b3", fetch) == (
            ["b4"],
            None,
        )


def test_a_new_name_is_placed_in_the_container_of_the_call(h, iam, guard):
    alice = h.user("alice")
    h.register("ws-1")
    h.grant(
        alice.id,
        statement("Allow", ["store:*"], ["${scope}/*"]),
        scope=WS1,
    )
    with h.as_(alice), _in(WS1):
        commit = guard.create(
            "Create", "item", ["ns", "x"], prefix=("namespace", ["ns"])
        )
        commit()
    assert iam.resolve_placement("store", "ns") == WS1
    assert iam.resolve_placement("store", "ns/y") == WS1
    # In no container: no create right on the platform.
    with h.as_(alice), _in(None), pytest.raises(ResourceNotFoundError):
        guard.create("Create", "item", ["other", "x"], prefix=("namespace", ["other"]))
    # A container IAM does not know places on the platform: not found either.
    with h.as_(alice), _in(workspace("ws-9")), pytest.raises(ResourceNotFoundError):
        guard.create("Create", "item", ["other", "x"], prefix=("namespace", ["other"]))
    assert iam.placement_of("store", "other") is None


def test_a_placed_prefix_refuses_another_container(h, iam, guard):
    alice = h.user("alice")
    h.register("ws-1")
    h.register("ws-2")
    h.grant(alice.id, statement("Allow", ["store:*"], ["*"]))
    with internal_call():
        iam.put_placement("store", "ns", WS1)
        iam.put_placement("store", "ns/*", WS1)
    with h.as_(alice), _in(WS2), pytest.raises(PermissionDeniedError):
        guard.create("Create", "item", ["ns", "x"], prefix=("namespace", ["ns"]))
    with h.as_(alice), _in(WS1):
        guard.create("Create", "item", ["ns", "x"], prefix=("namespace", ["ns"]))()
    assert iam.resolve_placement("store", "ns/x") == WS1


def test_a_child_takes_its_containers_placement_whatever_the_target(h, iam, guard):
    with internal_call():
        iam.put_placement("store", "shared", PLATFORM)
        iam.put_placement("store", "shared/*", PLATFORM)
    member = h.user("member")
    h.grant(member.id, statement("Allow", ["store:*"], ["*"]))
    h.register("ws-1")
    with h.as_(member), _in(WS1):
        # A platform id prefix: a workspace caller cannot claim a name in it.
        with pytest.raises(PermissionDeniedError):
            guard.create(
                "Create", "item", ["shared", "x"], prefix=("namespace", ["shared"])
            )
        # An existing resource ignores the container of the call.
        guard.create(
            "Create",
            "item",
            ["shared", "x"],
            prefix=("namespace", ["shared"]),
            exists=lambda: True,
        )
    with h.as_(member), _in(None):
        guard.create(
            "Create", "item", ["shared", "x"], prefix=("namespace", ["shared"])
        )()
    assert iam.resolve_placement("store", "shared/x") == PLATFORM


def test_an_existing_unplaced_id_prefix_is_the_platforms(h, iam, guard):
    member = h.user("member")
    h.register("ws-1")
    h.grant(member.id, statement("Allow", ["store:*"], ["*"]))
    with h.as_(member), _in(WS1), pytest.raises(PermissionDeniedError):
        guard.create(
            "Create",
            "item",
            ["legacy", "x"],
            prefix=("namespace", ["legacy"]),
            prefix_exists=lambda: True,
        )
    assert iam.placement_of("store", "legacy") is not None
    assert iam.resolve_placement("store", "legacy/x") == PLATFORM


def test_forget_drops_an_id_prefixs_placements(iam, h, guard):
    h.register("ws-1")
    with internal_call():
        iam.put_placement("store", "ns", WS1)
        iam.put_placement("store", "ns/*", WS1)
    guard.forget("namespace", ["ns"])
    assert iam.placement_of("store", "ns") is None
    assert iam.placement_of("store", "ns/x") is None


def test_own_storage_runs_as_the_engine_for_no_user_in_no_container(h):
    seen = []

    class Storage:
        def call(self):
            seen.append(current_call_context())

        def stream(self):
            for item in (1, 2):
                seen.append(current_call_context())
                yield item

    bob = h.user("bob")
    with h.as_(bob), _in(WS1):
        storage = own_storage(Storage())
        storage.call()
        assert list(storage.stream()) == [1, 2]
    assert len(seen) == 3
    for context in seen:
        assert context.principal.name == "engine"
        assert context.on_behalf_of is None and context.container is None


def test_own_storage_runs_a_context_managers_body_as_the_engine(h):
    """``KeyValueService.lock`` and the object streams run their body on entry
    and exit, after the call returned: those run as the engine too."""
    seen = []

    class Storage:
        @contextmanager
        def lock(self):
            seen.append(("enter", current_call_context().principal.name))
            try:
                yield "held"
            finally:
                seen.append(("exit", current_call_context().principal.name))

        def plain_file(self):
            return io.BytesIO(b"x")

    bob = h.user("bob")
    with h.as_(bob), _in(WS1):
        storage = own_storage(Storage())
        with storage.lock() as held:
            assert held == "held"
            # The caller's own code in the block is still the caller's.
            assert current_call_context().principal != service_account("engine")
        assert storage.plain_file().read() == b"x"
    assert seen == [("enter", "engine"), ("exit", "engine")]
