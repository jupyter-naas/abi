"""Who a person is connected to, read from the datasets only.

The ``connections`` table holds one row per person and connection, in both
directions (``export_people_from_graph.connection_rows``), merged across every
dataset the workspace may read (``graph_datasets.merge_tables``). Nothing here
reads a graph: the count on a search result, the Connections tab and its
network are a filter on ``slug`` plus a lookup of the peers' people rows.

A connection whose peer no dataset lists (the export named someone the
workspace may not read) is not counted and not shown: a count the list cannot
back would be a number nobody can open.
"""

from __future__ import annotations

from typing import Any

from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts import (
    datasets as ds,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.graph_payload import (
    _entity_node,
    build_graph_page_payload,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.memory_people_store import (
    PeopleStore,
)
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.network_payload import (
    _props,
    _relation,
    network_view_config,
    organization_id,
)

# The Connections network draws the person and this many of their connections,
# most connected first: each brings an act of connection and an act of working,
# so past that the canvas is a hairball.
NETWORK_SIZE = 60
CONNECTION_CLASS = "linkedin:ActOfConnection"


class PersonNotFoundError(LookupError):
    """No dataset lists a person under this slug."""


def _connection_rows(
    store: PeopleStore, config: dict[str, Any], slugs: list[str]
) -> dict[str, list[dict[str, Any]]]:
    data = config["data"]
    table = data["tables"].get("connections")
    if not table or not slugs:
        return {}
    try:
        return ds.fetch_children(
            store,
            namespace=data["namespace"],
            table=table,
            slugs=slugs,
            order_by="peer_slug",
        )
    except ds.DatasetsMissingError:
        # A dataset written before connections existed has no such table.
        return {}


def _people(
    store: PeopleStore, config: dict[str, Any], slugs: list[str]
) -> dict[str, dict[str, Any]]:
    if not slugs:
        return {}
    data = config["data"]
    rows = ds.fetch_people(
        store,
        namespace=data["namespace"],
        table=data["tables"]["people"],
        where=f"slug IN ({ds.slug_list(sorted(set(slugs)))})",
    )
    return {row["slug"]: row for row in rows}


def connection_counts(
    store: PeopleStore, config: dict[str, Any], slugs: list[str]
) -> dict[str, int]:
    """How many listed people each of *slugs* is connected to. Zero is left out."""
    rows = _connection_rows(store, config, slugs)
    peers = {row["peer_slug"] for items in rows.values() for row in items}
    listed = set(_people(store, config, sorted(peers)))
    counts: dict[str, int] = {}
    for slug, items in rows.items():
        count = len({row["peer_slug"] for row in items if row["peer_slug"] in listed})
        if count:
            counts[slug] = count
    return counts


def _current_position(
    store: PeopleStore, config: dict[str, Any], slugs: list[str]
) -> dict[str, dict[str, Any]]:
    """Each person's most recent act of working (experience row seq 0)."""
    data = config["data"]
    grouped = ds.fetch_children(
        store,
        namespace=data["namespace"],
        table=data["tables"]["experience"],
        slugs=slugs,
    )
    return {slug: items[0] for slug, items in grouped.items() if items}


def _connection(
    person: dict[str, Any],
    position: dict[str, Any] | None,
    connected_on: Any,
) -> dict[str, Any]:
    return {
        "slug": person.get("slug"),
        "full_name": person.get("full_name"),
        "photo_url": person.get("photo_url"),
        "organization": (position or {}).get("organization")
        or person.get("organization"),
        "organization_logo": (position or {}).get("organization_logo")
        or person.get("organization_logo"),
        "position": (position or {}).get("title") or person.get("headline"),
        "country_code": person.get("country_code"),
        "connected_on": str(connected_on)[:10] if connected_on else None,
    }


def connections(
    store: PeopleStore, config: dict[str, Any], *, slug: str
) -> dict[str, Any]:
    """The person and everyone listed they are connected to, most connected first."""
    person = _people(store, config, [slug]).get(slug)
    if person is None:
        raise PersonNotFoundError(slug)
    rows = _connection_rows(store, config, [slug]).get(slug, [])
    dates: dict[str, Any] = {}
    for row in rows:
        dates.setdefault(row["peer_slug"], row.get("connected_on"))
    peers = _people(store, config, sorted(dates))
    positions = _current_position(store, config, sorted(peers))
    counts = connection_counts(store, config, sorted(peers))
    results = [
        {
            **_connection(peers[peer], positions.get(peer), dates[peer]),
            "connections_count": counts.get(peer, 0),
        }
        for peer in peers
    ]
    # Most connected first; then most recent, undated last; by name within a date.
    results.sort(key=lambda item: str(item.get("full_name") or ""))
    results.sort(key=lambda item: item["connected_on"] or "", reverse=True)
    results.sort(key=lambda item: item["connected_on"] is None)
    results.sort(key=lambda item: -item["connections_count"])
    return {
        "person": _connection(
            person, _current_position(store, config, [slug]).get(slug), None
        ),
        "total": len(results),
        "results": results,
    }


def _network_labels(everyone: list[dict[str, Any]]) -> dict[str, str]:
    """A canvas label per slug. The graph page keys a person on their label:
    two people who share a name would be drawn as one, so the second is told
    apart by employer, then by slug."""
    labels: dict[str, str] = {}
    for item in everyone:
        label = item.get("full_name") or item["slug"]
        if label in labels.values():
            label = f"{label} ({item.get('organization') or item['slug']})"
        if label in labels.values():
            label = f"{label} [{item['slug']}]"
        labels[item["slug"]] = label
    return labels


def _connection_act(
    act_id: str, first: str, second: str, connected_on: str | None
) -> dict[str, Any]:
    return _entity_node(
        act_id,
        label=f"Connection {connected_on}" if connected_on else "Connection",
        class_uri=CONNECTION_CLASS,
        class_label="Act of Connection",
        bfo_bucket="Process",
        started_at=connected_on,
        properties=_props(
            ("abi:hasParticipant", "participant", first),
            ("abi:hasParticipant", "participant", second),
            ("abi:instant_date", "connected on", connected_on),
        ),
    )


def _working_act(act_id: str, worker: str, position: dict[str, Any]) -> dict[str, Any]:
    title = position.get("title") or "Act of Working"
    organization = position.get("organization")
    start = position.get("start_date")
    end = position.get("end_date")
    return _entity_node(
        act_id,
        label=f"{title} @ {organization}" if organization else title,
        class_uri="abi:ActOfWorking",
        class_label="Act of Working",
        bfo_bucket="Process",
        is_working_hub=True,
        started_at=str(start)[:10] if start else None,
        ended_at=str(end)[:10] if end else None,
        properties=_props(
            ("abi:isActOfWorkingOf", "worker", worker),
            ("abi:forOrganization", "organization", organization),
            ("abi:job_title", "job title", position.get("title")),
            ("abi:hasFirstInstant", "start", str(start)[:10] if start else None),
            ("abi:hasLastInstant", "end", str(end)[:10] if end else None),
        ),
    )


def connections_network(
    store: PeopleStore, config: dict[str, Any], *, slug: str
) -> dict[str, Any]:
    """The graph page payload of one person and their connections, drawn as the
    processes that tie them: each act of connection between two drawn people
    (the person's own, and those among their connections), and each person's
    current act of working with the organization it is for. Two people working
    at the same organization meet at its node, through their own acts."""
    found = connections(store, config, slug=slug)
    person = found["person"]
    shown = found["results"][:NETWORK_SIZE]
    everyone = [person, *shown]
    labels = _network_labels(everyone)
    payload = build_graph_page_payload(
        [{"personLabel": labels[item["slug"]]} for item in everyone]
    )
    slugs = {label: slug for slug, label in labels.items()}
    for drawn in payload["people"]:
        drawn["slug"] = slugs.get(drawn["id"])

    entities: dict[str, dict[str, Any]] = {}
    relations: list[dict[str, Any]] = []

    # WHO knows whom: one act per pair of drawn people, whichever export it
    # came from (the table holds both directions; the pair is keyed once).
    drawn_slugs = sorted(labels)
    for owner, rows in _connection_rows(store, config, drawn_slugs).items():
        for row in rows:
            peer = row["peer_slug"]
            if peer not in labels or peer == owner:
                continue
            first, second = sorted((owner, peer))
            act_id = f"connection:{first}|{second}"
            if act_id in entities:
                continue
            connected_on = (
                str(row["connected_on"])[:10] if row.get("connected_on") else None
            )
            entities[act_id] = _connection_act(
                act_id, labels[first], labels[second], connected_on
            )
            for participant in (first, second):
                relations.append(
                    _relation(
                        act_id,
                        labels[participant],
                        "abi:hasParticipant",
                        "has participant",
                    )
                )

    # WHERE they work: the current act of working, for its organization.
    positions = _current_position(store, config, drawn_slugs)
    for item in everyone:
        label = labels[item["slug"]]
        position = positions.get(item["slug"]) or {}
        organization = (
            position.get("organization") or item.get("organization") or ""
        ).strip()
        if not organization:
            continue
        position = {**position, "organization": organization}
        act_id = f"working:{item['slug']}"
        entities[act_id] = _working_act(act_id, label, position)
        relations.append(
            _relation(label, act_id, "abi:hasActOfWorking", "has act of working")
        )
        org_id = organization_id(organization)
        node = entities.setdefault(
            org_id,
            _entity_node(
                org_id,
                label=organization,
                class_uri="abi:Organization",
                class_label="Organization",
                bfo_bucket="Material Entity",
                properties=_props(("rdfs:label", "name", organization)),
            ),
        )
        logo = position.get("organization_logo") or item.get("organization_logo")
        if logo and not node.get("image"):
            node["image"] = logo
        relations.append(
            _relation(act_id, org_id, "abi:forOrganization", "for organization")
        )

    view_config = network_view_config(config)
    view_config["graph"].update(
        default_distance=4,
        max_distance=4,
        params_session_key="people-connections-graph-params-v2",
    )
    return {
        "person": person,
        "total": found["total"],
        "shown": len(shown),
        "root": labels[person["slug"]],
        "data": {
            **payload,
            "entities": sorted(entities.values(), key=lambda entity: entity["label"]),
            "relations": relations,
            "allRelations": relations,
        },
        "config": view_config,
    }
