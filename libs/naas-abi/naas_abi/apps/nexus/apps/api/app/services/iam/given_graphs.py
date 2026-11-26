"""The graphs a workspace is given outside it, and what it closes of its own: the Graphs
part of its offer (ADR ``20261125_offer_gives_outside_resources``).

"<W> access" may hold Allow statements naming resources outside W, absolute names and no
``${scope}``: IAM reads them as grants to the people of W (the members of its membership
groups) while they belong to W, each action within their level there (core "Given
statements"). A graph shared with W is one of them; what W closes of its own graphs is a
Deny within ``${scope}``, which applies to W's people as any Deny of W's bound.

| Section | Effect | Actions | Resources |
|---|---|---|---|
| ``GivenGraphs`` (parts ``GivenGraphs2``...) | Allow | the graph actions at the list and read levels | each graph W reads or writes, by its absolute name |
| ``GivenGraphsWrite`` (parts too) | Allow | ``Insert``, ``Remove`` | each graph W writes |
| ``GivenGraphsAll`` | Allow | as ``GivenGraphs`` | every graph of W's organization (``<O>/triple_store:graph/*``, ``<O>/*/triple_store:graph/*``; W's own for a workspace in none) and the schema graph: "read all graphs, including future graphs" |
| ``OfferGraphsDeny`` | Deny | ``CreateGraph`` | ``${scope}/triple_store:graph/*``: W creates no graph |
| ``OfferGraphsDeny2``... | Deny | every graph action | ``${scope}/triple_store:graph/<iri>`` of each graph W owns and does not share with itself, and the name of "a new graph" (``NEW_GRAPH``), which says W excludes its own graphs |

A graph is named as IAM placed it: ``<container>/triple_store:graph/<iri>`` (or
``abi:triple_store:graph/<iri>`` at the platform) when an administrator shares it, which
they must hold (IAM's held check), or wherever it is placed (``abi:triple_store:graph/<iri>``
and ``abi:*/triple_store:graph/<iri>``, ``anywhere_names``) when Nexus moves an older
assignment or a configuration's. Each name reads back as its graph's IRI; changing the
sections keeps the names of the graphs that stay, so a workspace's admin removes one
graph without being asked to hold the others.

The level caps each person: a Viewer of W lists and reads, a Member and an admin write
too. Never ``ClearGraph`` nor ``DropGraph``: a graph's life stays with its workspace. Nexus's
own graphs are never given.

Pure: no IAM, no database.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from typing import Any
from urllib.parse import unquote

from naas_abi.apps.nexus.apps.api.app.services.iam.names import org_container, org_of
from naas_abi.apps.nexus.graph_policy_config import (
    NEXUS_GRAPH,
    SCHEMA_GRAPH,
    WorkspaceGraphPolicyConfig,
    is_nexus_system_graph,
    without_system_graphs,
)
from naas_abi_core.services.iam.names import anywhere, encode_id, resource_name
from naas_abi_core.services.iam.policy import MAX_PATTERNS
from naas_abi_core.services.triple_store.iam_catalog import CATALOG, GRAPH, SERVICE


def _actions(*levels: str, creates: bool = False) -> list[str]:
    return [
        CATALOG.qualified(a.name)
        for a in CATALOG.actions
        if GRAPH in a.resource_types and a.level in levels and a.creates == creates
    ]


READ_ACTIONS = _actions("list", "read")
WRITE_ACTIONS = _actions("write")
CREATE_ACTIONS = _actions("write", creates=True)
ALL_ACTIONS = _actions("list", "read", "write", "admin") + CREATE_ACTIONS

READ_SID = "GivenGraphs"
WRITE_SID = "GivenGraphsWrite"
ALL_SID = "GivenGraphsAll"
DENY_SID = "OfferGraphsDeny"
SIDS = (READ_SID, WRITE_SID, ALL_SID, DENY_SID)

SCOPE = "${scope}/"
STEP = f"{SERVICE}:{GRAPH}/"
# Any graph IRI of a workspace stands for "a new graph there" (``graph_iam.NEW_GRAPH``).
NEW_GRAPH = "urn:nexus:new-graph"
EVERY_GRAPH_HERE = f"{SCOPE}{STEP}*"

NameOf = Callable[[str], Sequence[str]]


# -- the names ---------------------------------------------------------------------------


def graph_id(iri: str) -> str:
    return encode_id(iri, "opaque")


def anywhere_names(iri: str) -> list[str]:
    """The graph wherever IAM placed it, at the platform or in any container: what an
    older assignment named (a graph keeps its identity if it moves)."""
    return anywhere(f"{STEP}{graph_id(iri)}")


def name_in(container: str, iri: str) -> str:
    """The graph's name in ``container`` (``abi:`` for the platform)."""
    return resource_name(SERVICE, GRAPH, iri, kind="opaque", container=container)


def closed_name(iri: str) -> str:
    """One of W's own graphs, as a Deny of W's bound names it."""
    return f"{SCOPE}{STEP}{graph_id(iri)}"


def read_all_names(container: str) -> list[str]:
    """Every graph of the organization of the workspace ``container`` (its own, for a
    workspace in none), and the store's schema graph: what ``read_all`` reads."""
    organization = org_of(container)
    if organization is None:
        mine = [f"{container}/{STEP}*"]
    else:
        org = org_container(organization)
        mine = [f"{org}/{STEP}*", f"{org}/*/{STEP}*"]
    return [*mine, *anywhere_names(SCHEMA_GRAPH)]


def iri_of(pattern: str) -> str | None:
    """The graph a name stands for; None for a pattern of many graphs."""
    _head, step, rest = pattern.rpartition(STEP)
    if not step or not rest or "*" in rest or "?" in rest or "/" in rest:
        return None
    return unquote(rest)


def iris_of(patterns: Iterable[str]) -> set[str]:
    return {iri for p in patterns if (iri := iri_of(p)) is not None}


# -- the statements ----------------------------------------------------------------------


def _parts(
    sid: str, effect: str, actions: list[str], resources: list[str], *, first: int = 1
) -> list[dict[str, Any]]:
    statements = []
    for index, start in enumerate(range(0, len(resources), MAX_PATTERNS)):
        number = first + index
        statements.append(
            {
                "sid": sid if number == 1 else f"{sid}{number}",
                "effect": effect,
                "actions": list(actions),
                "resources": resources[start : start + MAX_PATTERNS],
            }
        )
    return statements


def statements(
    read: Iterable[str],
    write: Iterable[str],
    read_all: Iterable[str],
    no_create: bool,
    closed: Iterable[str],
) -> list[dict[str, Any]]:
    """The Graphs sections of an offer: the given Allows, in parts past
    ``policy.MAX_PATTERNS`` names, then W's Denies."""
    found = [
        *_parts(READ_SID, "Allow", READ_ACTIONS, sorted(read)),
        *_parts(WRITE_SID, "Allow", WRITE_ACTIONS, sorted(write)),
        *_parts(ALL_SID, "Allow", READ_ACTIONS, sorted(read_all)),
    ]
    if no_create:
        found.append(
            {
                "sid": DENY_SID,
                "effect": "Deny",
                "actions": list(CREATE_ACTIONS),
                "resources": [EVERY_GRAPH_HERE],
            }
        )
    found += _parts(DENY_SID, "Deny", ALL_ACTIONS, sorted(closed), first=2)
    return found


# -- the configuration -------------------------------------------------------------------


def _kept(iris: set[str], current: Iterable[str], name_of: NameOf) -> frozenset[str]:
    """The names of ``iris``: those ``current`` gives them, ``name_of`` for the others."""
    kept = {p for p in current if iri_of(p) in iris}
    named = iris_of(kept)
    return frozenset(kept | {n for iri in sorted(iris - named) for n in name_of(iri)})


def fields_of(
    config: WorkspaceGraphPolicyConfig,
    *,
    container: str,
    owned: Iterable[str] = (),
    name_of: NameOf = anywhere_names,
    current: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """The ``Offer`` fields (``graphs_read``, ``graphs_write``, ``graphs_all``,
    ``graphs_no_create``, ``graphs_closed``) saying what ``config`` says for the workspace
    ``container``. ``owned``: the graphs it owns, for the ones it excludes. ``current``:
    the fields it has, whose names are kept for the graphs that stay (``name_of`` names
    the others)."""
    current = current or {}
    shared = without_system_graphs(set(config.read) | set(config.write)) - {NEXUS_GRAPH}
    written = without_system_graphs(set(config.write)) - {SCHEMA_GRAPH}
    read_all: frozenset[str] = frozenset()
    if config.read_all:
        read_all = frozenset(current.get("graphs_all") or ()) or frozenset(
            read_all_names(container)
        )
    closed: frozenset[str] = frozenset()
    if not config.include_owned:
        # Reading all of its organization's graphs reads its own: none is closed.
        excluded = set() if config.read_all else set(owned) - shared
        closed = frozenset({closed_name(NEW_GRAPH), *(closed_name(i) for i in excluded)})
    return {
        "graphs_read": _kept(shared, current.get("graphs_read") or (), name_of),
        "graphs_write": _kept(written, current.get("graphs_write") or (), name_of),
        "graphs_all": read_all,
        "graphs_no_create": not (config.allow_create and config.include_owned),
        "graphs_closed": closed,
    }


def config_of(fields: Mapping[str, Any] | Any) -> WorkspaceGraphPolicyConfig:
    """The configuration the Graphs sections of an offer say (an ``Offer`` or its
    fields)."""

    def get(name: str) -> Any:
        return fields.get(name) if isinstance(fields, Mapping) else getattr(fields, name)

    def graphs(name: str) -> list[str]:
        return sorted(
            iri
            for iri in iris_of(get(name) or ())
            if not is_nexus_system_graph(iri) and iri.startswith(("https://", "http://", "urn:"))
        )

    include_owned = not get("graphs_closed")
    return WorkspaceGraphPolicyConfig(
        read_all=bool(get("graphs_all")),
        read=graphs("graphs_read"),
        write=[iri for iri in graphs("graphs_write") if iri != SCHEMA_GRAPH],
        include_owned=include_owned,
        allow_create=include_owned and not get("graphs_no_create"),
    )


def summary(fields: Mapping[str, Any] | Any) -> dict[str, Any]:
    """What the offer editor shows of the Graphs part: how many graphs W reads and
    writes, and its switches."""
    config = config_of(fields)
    return {
        "read": len(set(config.read) | set(config.write)),
        "write": len(config.write),
        "read_all": config.read_all,
        "include_owned": config.include_owned,
        "allow_create": config.allow_create,
    }


__all__ = [
    "ALL_ACTIONS",
    "ALL_SID",
    "CREATE_ACTIONS",
    "DENY_SID",
    "NEW_GRAPH",
    "READ_ACTIONS",
    "READ_SID",
    "SIDS",
    "WRITE_ACTIONS",
    "WRITE_SID",
    "anywhere_names",
    "closed_name",
    "config_of",
    "fields_of",
    "iri_of",
    "iris_of",
    "name_in",
    "read_all_names",
    "statements",
    "summary",
]
