"""The Maps items a workspace uses without owning them: the Maps part of its offer (ADR
``20261125_offer_gives_outside_resources``, "Maps").

Two kinds of items are not a workspace's own: the deployment's feeds and basemaps (seeds,
copied into each workspace that may use them) and the feeds and basemaps another workspace
shares with it. Which of them a workspace may use was ``maps_grants`` (an item's list of
workspaces); it is now its offer "<W> access", one place per workspace. Its people read
them within their level; the workspace hides any of them as it likes (``maps_settings``,
a display choice, not the offer's).

| Section | Effect | Actions | Resources |
|---|---|---|---|
| ``GivenMaps`` (parts ``GivenMaps2``...) | Allow | ``ListLayouts``, ``GetLayout`` | the deployment's feeds given, ``abi:nexus:layout/*`` (every one, the ones added later too) or ``abi:nexus:layout/<id>``; another workspace's feed shared with W, ``<V>/nexus:layout/<id>`` |
| ``GivenBasemaps`` (parts) | Allow | ``ListBasemaps``, ``GetBasemap`` | the same for basemaps (``nexus:basemap``) |
| ``OfferMapsDeny`` (parts) | Deny | ``ListLayouts``, ``GetLayout`` | ``${scope}/nexus:layout/<id>``: a deployment feed W does not use, though every one is given |
| ``OfferBasemapsDeny`` (parts) | Deny | ``ListBasemaps``, ``GetBasemap`` | the same for basemaps |

The given sections are Allows on absolute names: IAM gives them to W's people while they
belong to W, within their level (core "Given statements"), and whoever writes one must hold
it: only the platform admin gives a deployment item, and an item of V is given by whoever
holds it in V (V's admins, its organization's). What W closes is a Deny of its bound, on
its own copy of the item: a workspace admin closes one, never reopens it. A feed's layers
follow their feed; built-in feeds and graph layers are never in it.

Nexus reads the part as the workspace's ``MapsAssignment`` (``assignment_of``): which
deployment items it seeds and lists, and which shared items it lists. Pure: no IAM, no
database.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam.names import (
    PLATFORM,
    SERVICE,
    nexus_resource,
    scoped_resource,
    workspace_of,
)
from naas_abi.apps.nexus.apps.api.app.services.maps.permissions.permissions__schema import (
    DEPLOYMENT,
    KIND_BASEMAP,
    KIND_LAYOUT,
    MapsAssignment,
)
from naas_abi_core.services.iam.policy import MAX_PATTERNS

KINDS = (KIND_LAYOUT, KIND_BASEMAP)
# What a given item lets W's people do: list and read it (Viewers do no more); its
# administration stays on W's own copy (``${scope}/nexus:<kind>/<id>``), its role's.
ACTIONS: dict[str, list[str]] = {
    KIND_LAYOUT: [f"{SERVICE}:ListLayouts", f"{SERVICE}:GetLayout"],
    KIND_BASEMAP: [f"{SERVICE}:ListBasemaps", f"{SERVICE}:GetBasemap"],
}
GIVEN_SID = {KIND_LAYOUT: "GivenMaps", KIND_BASEMAP: "GivenBasemaps"}
CLOSED_SID = {KIND_LAYOUT: "OfferMapsDeny", KIND_BASEMAP: "OfferBasemapsDeny"}
GIVEN_SIDS = frozenset(GIVEN_SID.values())
DENY_SIDS = frozenset(CLOSED_SID.values())
SIDS = (*GIVEN_SID.values(), *CLOSED_SID.values())
# The ``Offer`` fields: the given names, and the closed ones.
FIELDS = ("maps", "maps_closed")

SCOPE = "${scope}/"
EVERY = "*"

ContainerOf = Callable[[str], str | None]


# -- the names ---------------------------------------------------------------------------


def platform_name(kind: str, item_id: str) -> str:
    """A deployment item, at the platform: ``abi:nexus:<kind>/<id>``."""
    return nexus_resource(kind, id=item_id)


def every_name(kind: str) -> str:
    """Every deployment item of ``kind``, the ones added later too."""
    return f"{PLATFORM}{SERVICE}:{kind}/{EVERY}"


def shared_name(container: str, kind: str, item_id: str) -> str:
    """An item of the workspace ``container``, as IAM names it there."""
    return nexus_resource(kind, container=container, id=item_id)


def closed_name(kind: str, item_id: str) -> str:
    """W's own copy of a deployment item, as a Deny of W's bound names it."""
    return scoped_resource(kind, item_id)


def _step(rest: str) -> tuple[str, str] | None:
    kind, slash, item = rest.partition("/")
    if kind not in KINDS or not slash or not item or "/" in item or "?" in item:
        return None
    return kind, unquote(item)


def parse(name: str) -> tuple[str, str, str] | None:
    """``(kind, owner, id)`` a given name stands for: ``owner`` is ``""`` for the
    deployment, else the owning workspace; ``id`` ``*`` for every deployment item of the
    kind. None for any other name."""
    if name.startswith(SCOPE):
        return None
    platform = f"{PLATFORM}{SERVICE}:"
    if name.startswith(platform):
        # ``abi:nexus:layout/<id>``; a workspace in none is ``abi:nexus:workspace/...``.
        found = _step(name[len(platform) :])
        if found is not None and (found[1] == EVERY or "*" not in found[1]):
            return found[0], DEPLOYMENT, found[1]
    head, sep, rest = name.rpartition(f"/{SERVICE}:")
    if not sep or not head.startswith(PLATFORM):
        return None
    owner = workspace_of(head)
    found = _step(rest)
    if owner is None or found is None or "*" in found[1]:
        return None
    return found[0], owner, found[1]


def closed_of(name: str) -> tuple[str, str] | None:
    """``(kind, id)`` a closed name stands for; None for any other name."""
    prefix = f"{SCOPE}{SERVICE}:"
    if not name.startswith(prefix):
        return None
    found = _step(name[len(prefix) :])
    return None if found is None or "*" in found[1] else found


# -- the statements ----------------------------------------------------------------------


def _parts(sid: str, effect: str, actions: list[str], resources: list[str]) -> list[dict]:
    return [
        {
            "sid": f"{sid}{start // MAX_PATTERNS + 1}" if start else sid,
            "effect": effect,
            "actions": list(actions),
            "resources": resources[start : start + MAX_PATTERNS],
        }
        for start in range(0, len(resources), MAX_PATTERNS)
    ]


def _kind_of(name: str) -> str | None:
    found = parse(name) or closed_of(name)
    return found[0] if found else None


def statements(maps: Iterable[str], closed: Iterable[str]) -> list[dict[str, Any]]:
    """The Maps sections of an offer: the given Allows by kind, then W's Denies, each in
    parts past ``policy.MAX_PATTERNS`` names. A name of neither kind is not written."""
    maps, closed = set(maps), set(closed)
    found: list[dict[str, Any]] = []
    for kind in KINDS:
        names = sorted(n for n in maps if _kind_of(n) == kind)
        found += _parts(GIVEN_SID[kind], "Allow", ACTIONS[kind], names)
    for kind in KINDS:
        names = sorted(n for n in closed if _kind_of(n) == kind)
        found += _parts(CLOSED_SID[kind], "Deny", ACTIONS[kind], names)
    return found


# -- the assignment ----------------------------------------------------------------------


def _get(fields: Mapping[str, Any] | Any, name: str) -> frozenset[str]:
    value = fields.get(name) if isinstance(fields, Mapping) else getattr(fields, name)
    return frozenset(value or ())


def assignment_of(fields: Mapping[str, Any] | Any) -> MapsAssignment:
    """What the Maps sections of an offer (an ``Offer`` or its fields) say W may use."""
    every: set[str] = set()
    platform: set[tuple[str, str]] = set()
    shared: set[tuple[str, str, str]] = set()
    for name in _get(fields, "maps"):
        found = parse(name)
        if found is None:
            continue
        kind, owner, item = found
        if owner != DEPLOYMENT:
            shared.add((kind, owner, item))
        elif item == EVERY:
            every.add(kind)
        else:
            platform.add((kind, item))
    closed = {pair for n in _get(fields, "maps_closed") if (pair := closed_of(n))}
    return MapsAssignment(
        every=frozenset(every),
        platform=frozenset(platform),
        closed=frozenset(closed),
        shared=frozenset(shared),
    )


def fields_of(assignment: MapsAssignment, *, container_of: ContainerOf) -> dict[str, Any]:
    """The ``Offer`` fields (``maps``, ``maps_closed``) saying ``assignment``; an item
    shared by a workspace ``container_of`` does not know (gone) is left out."""
    maps = {every_name(kind) for kind in assignment.every}
    maps |= {platform_name(kind, item) for kind, item in assignment.platform}
    for kind, owner, item in assignment.shared:
        container = container_of(owner)
        if container is not None:
            maps.add(shared_name(container, kind, item))
    closed = {closed_name(kind, item) for kind, item in assignment.closed}
    return {"maps": frozenset(maps), "maps_closed": frozenset(closed)}


def every_platform_map() -> MapsAssignment:
    """Every deployment feed and basemap, the ones added later too: what a workspace was
    given before its offer said it (``maps_grants`` with no row), and a new one is."""
    return MapsAssignment(every=frozenset(KINDS))


def with_item(
    fields: Mapping[str, Any] | Any,
    kind: str,
    item_id: str,
    *,
    owner_container: str | None,
    given: bool,
) -> dict[str, Any]:
    """The Maps fields with one item given or taken, the rest kept as named.
    ``owner_container`` is the owning workspace's container, None for a deployment item:
    one given by name is named; one given with every item of its kind is closed or
    reopened."""
    maps, closed = set(_get(fields, "maps")), set(_get(fields, "maps_closed"))
    if owner_container is not None:
        name = shared_name(owner_container, kind, item_id)
        (maps.add if given else maps.discard)(name)
        return {"maps": frozenset(maps), "maps_closed": frozenset(closed)}
    every = every_name(kind) in maps
    if given:
        closed.discard(closed_name(kind, item_id))
        if not every:
            maps.add(platform_name(kind, item_id))
    else:
        maps.discard(platform_name(kind, item_id))
        if every:
            closed.add(closed_name(kind, item_id))
    return {"maps": frozenset(maps), "maps_closed": frozenset(closed)}


def summary(fields: Mapping[str, Any] | Any) -> dict[str, Any]:
    """What the offer editor shows of the Maps part, by kind (``feeds``, ``basemaps``):
    whether every deployment item is given, how many by name and how many it closes, and
    how many other workspaces' items are shared with it."""
    assignment = assignment_of(fields)
    found: dict[str, Any] = {}
    for kind, key in ((KIND_LAYOUT, "feeds"), (KIND_BASEMAP, "basemaps")):
        found[key] = {
            "every": kind in assignment.every,
            "named": sum(1 for k, _i in assignment.platform if k == kind),
            "closed": sum(1 for k, _i in assignment.closed if k == kind),
            "shared": len(assignment.shared_of(kind)),
        }
    return found


__all__ = [
    "ACTIONS",
    "CLOSED_SID",
    "DENY_SIDS",
    "FIELDS",
    "GIVEN_SID",
    "GIVEN_SIDS",
    "KINDS",
    "SIDS",
    "assignment_of",
    "closed_name",
    "closed_of",
    "every_name",
    "every_platform_map",
    "fields_of",
    "parse",
    "platform_name",
    "shared_name",
    "statements",
    "summary",
    "with_item",
]
