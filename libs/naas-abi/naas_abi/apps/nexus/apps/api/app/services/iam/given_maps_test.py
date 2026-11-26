"""The Maps part of a workspace's offer (``given_maps``): the platform's feeds and basemaps
it is given (every one of a kind, or by id), those it closes within ``${scope}``, and the
feeds and basemaps other workspaces share with it, by their absolute names. Pure."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.iam import given_maps
from naas_abi.apps.nexus.apps.api.app.services.iam.names import workspace_container
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    KIND_BASEMAP,
    KIND_LAYOUT,
    MapsAssignment,
)
from naas_abi_core.services.iam.policy import MAX_PATTERNS, parse_policy_document

V = workspace_container("org-1", "ws-v")
SOLO = workspace_container(None, "ws-solo")


def _containers(workspace: str) -> str | None:
    return {"ws-v": V, "ws-solo": SOLO}.get(workspace)


def test_the_names_say_what_they_give_and_read_back():
    assert given_maps.platform_name(KIND_LAYOUT, "osm") == "abi:nexus:layout/osm"
    assert given_maps.every_name(KIND_BASEMAP) == "abi:nexus:basemap/*"
    assert given_maps.shared_name(V, KIND_LAYOUT, "mine") == f"{V}/nexus:layout/mine"
    assert given_maps.closed_name(KIND_BASEMAP, "dark") == "${scope}/nexus:basemap/dark"
    assert given_maps.parse(given_maps.every_name(KIND_LAYOUT)) == (KIND_LAYOUT, "", "*")
    assert given_maps.parse("abi:nexus:basemap/dark") == (KIND_BASEMAP, "", "dark")
    assert given_maps.parse(given_maps.shared_name(V, KIND_LAYOUT, "a")) == (
        KIND_LAYOUT,
        "ws-v",
        "a",
    )
    assert given_maps.parse(given_maps.shared_name(SOLO, KIND_BASEMAP, "b")) == (
        KIND_BASEMAP,
        "ws-solo",
        "b",
    )
    assert given_maps.parse("${scope}/nexus:layout/x") is None
    assert given_maps.parse("abi:nexus:feed_layer/x") is None  # a layer follows its feed
    assert given_maps.parse(f"{V}/nexus:layout/*") is None  # never every item of a workspace
    assert given_maps.closed_of("${scope}/nexus:layout/x") == (KIND_LAYOUT, "x")
    assert given_maps.closed_of("abi:nexus:layout/x") is None


def test_an_assignment_becomes_the_maps_sections_and_back():
    assignment = MapsAssignment(
        every=frozenset({KIND_LAYOUT}),
        platform=frozenset({(KIND_BASEMAP, "dark")}),
        closed=frozenset({(KIND_LAYOUT, "narrowed")}),
        shared=frozenset({(KIND_LAYOUT, "ws-v", "mine"), (KIND_BASEMAP, "ws-solo", "sat")}),
    )
    fields = given_maps.fields_of(assignment, container_of=_containers)
    assert fields == {
        "maps": frozenset(
            {
                "abi:nexus:layout/*",
                "abi:nexus:basemap/dark",
                f"{V}/nexus:layout/mine",
                f"{SOLO}/nexus:basemap/sat",
            }
        ),
        "maps_closed": frozenset({"${scope}/nexus:layout/narrowed"}),
    }
    assert given_maps.assignment_of(fields) == assignment
    statements = given_maps.statements(fields["maps"], fields["maps_closed"])
    by_sid = {s["sid"]: s for s in statements}
    assert list(by_sid) == ["GivenMaps", "GivenBasemaps", "OfferMapsDeny"]
    assert by_sid["GivenMaps"] == {
        "sid": "GivenMaps",
        "effect": "Allow",
        "actions": ["nexus:ListLayouts", "nexus:GetLayout"],
        "resources": sorted(["abi:nexus:layout/*", f"{V}/nexus:layout/mine"]),
    }
    assert by_sid["GivenBasemaps"]["actions"] == ["nexus:ListBasemaps", "nexus:GetBasemap"]
    assert by_sid["OfferMapsDeny"] == {
        "sid": "OfferMapsDeny",
        "effect": "Deny",
        "actions": ["nexus:ListLayouts", "nexus:GetLayout"],
        "resources": ["${scope}/nexus:layout/narrowed"],
    }
    # Given: absolute names only; closed: within the workspace only.
    assert all("${" not in r for s in statements if s["effect"] == "Allow" for r in s["resources"])
    parse_policy_document({"version": "2026-10-13", "statements": statements})


def test_a_section_past_the_pattern_limit_is_written_in_parts():
    names = frozenset(
        given_maps.shared_name(V, KIND_LAYOUT, f"f{i:03}") for i in range(MAX_PATTERNS + 5)
    )
    closed = frozenset(given_maps.closed_name(KIND_BASEMAP, f"b{i:03}") for i in range(130))
    statements = given_maps.statements(names, closed)
    assert [s["sid"] for s in statements] == [
        "GivenMaps",
        "GivenMaps2",
        "OfferBasemapsDeny",
        "OfferBasemapsDeny2",
    ]
    assert {r for s in statements[:2] for r in s["resources"]} == names
    assert {r for s in statements[2:] for r in s["resources"]} == closed


def test_what_a_workspace_uses_of_the_platform_and_of_the_others():
    assignment = MapsAssignment(
        every=frozenset({KIND_LAYOUT}),
        platform=frozenset({(KIND_BASEMAP, "dark")}),
        closed=frozenset({(KIND_LAYOUT, "narrowed"), (KIND_BASEMAP, "dark")}),
        shared=frozenset({(KIND_LAYOUT, "ws-v", "mine")}),
    )
    assert assignment.gives_platform(KIND_LAYOUT, "added-later")
    assert not assignment.gives_platform(KIND_LAYOUT, "narrowed")
    # Closing wins over a name.
    assert not assignment.gives_platform(KIND_BASEMAP, "dark")
    assert not assignment.gives_platform(KIND_BASEMAP, "osm")
    assert assignment.shared_of(KIND_LAYOUT) == frozenset({("ws-v", "mine")})
    assert assignment.shared_of(KIND_BASEMAP) == frozenset()
    assert not MapsAssignment().gives_platform(KIND_LAYOUT, "osm")


def test_giving_and_taking_one_item_keeps_the_rest():
    every = given_maps.fields_of(given_maps.every_platform_map(), container_of=_containers)
    # Taking a platform item from a workspace given every one closes it there.
    taken = given_maps.with_item(every, KIND_LAYOUT, "x", owner_container=None, given=False)
    assert taken["maps"] == every["maps"]
    assert taken["maps_closed"] == {"${scope}/nexus:layout/x"}
    assert not given_maps.assignment_of(taken).gives_platform(KIND_LAYOUT, "x")
    # Giving it back reopens it.
    back = given_maps.with_item(taken, KIND_LAYOUT, "x", owner_container=None, given=True)
    assert back == every
    # A workspace given items by name: by name.
    named = given_maps.with_item(
        {"maps": frozenset(), "maps_closed": frozenset()},
        KIND_BASEMAP,
        "dark",
        owner_container=None,
        given=True,
    )
    assert named == {"maps": {"abi:nexus:basemap/dark"}, "maps_closed": frozenset()}
    assert given_maps.with_item(named, KIND_BASEMAP, "dark", owner_container=None, given=False) == {
        "maps": frozenset(),
        "maps_closed": frozenset(),
    }
    # Another workspace's item, by its name there.
    shared = given_maps.with_item(every, KIND_LAYOUT, "mine", owner_container=V, given=True)
    assert shared["maps"] == every["maps"] | {f"{V}/nexus:layout/mine"}
    assert given_maps.with_item(shared, KIND_LAYOUT, "mine", owner_container=V, given=False) == (
        every
    )


def test_the_summary_counts_what_the_editor_shows():
    fields = given_maps.fields_of(
        MapsAssignment(
            every=frozenset({KIND_LAYOUT}),
            platform=frozenset({(KIND_BASEMAP, "dark"), (KIND_BASEMAP, "osm")}),
            closed=frozenset({(KIND_LAYOUT, "narrowed")}),
            shared=frozenset({(KIND_LAYOUT, "ws-v", "mine")}),
        ),
        container_of=_containers,
    )
    assert given_maps.summary(fields) == {
        "feeds": {"every": True, "named": 0, "closed": 1, "shared": 1},
        "basemaps": {"every": False, "named": 2, "closed": 0, "shared": 0},
    }
    assert given_maps.summary({"maps": frozenset(), "maps_closed": frozenset()}) == {
        "feeds": {"every": False, "named": 0, "closed": 0, "shared": 0},
        "basemaps": {"every": False, "named": 0, "closed": 0, "shared": 0},
    }


def test_a_shared_item_whose_workspace_is_gone_is_left_out():
    assignment = MapsAssignment(shared=frozenset({(KIND_LAYOUT, "ws-gone", "x")}))
    assert given_maps.fields_of(assignment, container_of=_containers) == {
        "maps": frozenset(),
        "maps_closed": frozenset(),
    }
