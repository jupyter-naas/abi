"""The network behind a search: the people found and the organizations that connect them.

The people are the search's own page of results (same ranking, same facet), so
the "Graph" view shows who the list shows. What links them is their recorded
history, read from the datasets: the organizations they worked for, the clients
they were staffed at and the schools they studied at.
"""

from __future__ import annotations

from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService

from . import datasets as ds
from .search_payload import search

# How a person is tied to an organization, by the column the tie is read from.
LINKS = (
    ("experience", "organization", "organization", "worked_for"),
    ("experience", "client", "organization", "client_of"),
    ("education", "school", "school", "studied_at"),
)


def _org_id(kind: str, name: str) -> str:
    return f"{kind}:{name.strip().casefold()}"


def network(
    service: DatasetService,
    config: dict[str, Any],
    *,
    query: str = "",
    facet: str = "",
    page: int = 1,
) -> dict[str, Any]:
    """Nodes and edges for one page of search results.

    An organization or school is kept when it ties two of the people shown or
    more: one only a single person passed through says nothing about the group.
    When none does, every tie is kept, so a small or scattered result still has
    something to show.
    """
    found = search(service, config, query=query, facet=facet, page=page)
    people = found["results"]
    slugs = [person["slug"] for person in people]
    data = config["data"]
    children = {
        logical: ds.fetch_children(
            service,
            namespace=data["namespace"],
            table=data["tables"][logical],
            slugs=slugs,
        )
        for logical in {table for table, *_ in LINKS}
    }

    labels: dict[str, tuple[str, str]] = {}
    ties: dict[tuple[str, str, str], None] = {}
    for slug in slugs:
        for table, column, kind, relation in LINKS:
            for row in children[table].get(slug, []):
                name = (row.get(column) or "").strip()
                if not name:
                    continue
                org = _org_id(kind, name)
                labels.setdefault(org, (kind, name))
                ties[(f"person:{slug}", org, relation)] = None

    people_per_org: dict[str, set[str]] = {}
    for source, org, _ in ties:
        people_per_org.setdefault(org, set()).add(source)
    shared = {org for org, members in people_per_org.items() if len(members) > 1}
    kept = shared or set(people_per_org)

    nodes = [
        {
            "id": f"person:{person['slug']}",
            "kind": "person",
            "label": person.get("full_name") or person["slug"],
            "slug": person["slug"],
            "headline": person.get("headline"),
            "photo_url": person.get("photo_url"),
        }
        for person in people
    ]
    nodes += [
        {
            "id": org,
            "kind": labels[org][0],
            "label": labels[org][1],
            "people": len(people_per_org[org]),
        }
        for org in sorted(kept, key=lambda org: (-len(people_per_org[org]), org))
    ]
    edges = [
        {"source": source, "target": org, "relation": relation}
        for source, org, relation in ties
        if org in kept
    ]
    return {
        "query": found["query"],
        "facet": found["facet"],
        "total": found["total"],
        "page": found["page"],
        "pages": found["pages"],
        "nodes": nodes,
        "edges": edges,
    }
