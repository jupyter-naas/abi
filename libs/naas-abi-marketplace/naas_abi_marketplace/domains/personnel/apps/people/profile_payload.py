"""One profile, assembled from the nine tables into what the page renders.

Sections are built in the order the configuration asks for, and a section with
no rows is still present with its empty text. That distinction is the point: a
profile with no recommendations is not a profile whose recommendations we failed
to load, and the page says so rather than leaving a gap.
"""

from __future__ import annotations

import re
from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.personnel.apps.people import datasets as ds
from naas_abi_marketplace.domains.personnel.apps.people import sparql_queries as sq
from naas_abi_marketplace.domains.personnel.apps.people.profile_sparql import (
    competency_queries_for_profile,
)


def _knowledge_graph(config: dict[str, Any]) -> dict[str, str]:
    graph = (config.get("data") or {}).get("graph") or {}
    return {
        "iri": str(graph.get("iri") or sq.GRAPH_IRI),
        "label": str(graph.get("label") or "Personnel"),
    }

SLUG_PATTERN = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
CHILD_TABLES = (
    "experience",
    "education",
    "skills",
    "certifications",
    "languages",
    "recommendations",
    "interests",
    "sources",
)


class ProfileNotFoundError(LookupError):
    def __init__(self, slug: str) -> None:
        self.slug = slug
        super().__init__(f"No profile for {slug!r}")


def _iso(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)[:10]


def _period(start: Any, end: Any, duration: Any = None) -> dict[str, Any]:
    """Dates as given, plus the label a source stated. Nothing is computed.

    An open end means the person is still there, which is different from an end
    date nobody recorded; both arrive here as None, so the source's own duration
    label is kept rather than a span invented from the dates.
    """
    return {
        "start": _iso(start),
        "end": _iso(end),
        "duration": duration or None,
    }


def _experience(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Roles grouped under their employer, in the order the exporter set."""
    groups: list[dict[str, Any]] = []
    by_group: dict[Any, dict[str, Any]] = {}
    for row in rows:
        key = row.get("group_seq", row.get("seq"))
        group = by_group.get(key)
        if group is None:
            group = {
                "organization": row.get("organization"),
                "location": row.get("location"),
                "roles": [],
            }
            by_group[key] = group
            groups.append(group)
        group["roles"].append(
            {
                "title": row.get("title"),
                "description": row.get("description"),
                **_period(
                    row.get("start_date"),
                    row.get("end_date"),
                    row.get("duration_label"),
                ),
            }
        )
    for group in groups:
        starts = [role["start"] for role in group["roles"] if role["start"]]
        ends = [role["end"] for role in group["roles"] if role["end"]]
        group["start"] = min(starts) if starts else None
        # One open role makes the whole stay open.
        group["end"] = max(ends) if ends and len(ends) == len(group["roles"]) else None
    return groups


def _section_items(logical: str, rows: list[dict[str, Any]]) -> list[Any]:
    if logical == "experience":
        return _experience(rows)
    if logical == "skills":
        return [row["skill_name"] for row in rows if row.get("skill_name")]
    if logical == "education":
        return [
            {
                "school": row.get("school"),
                "degree": row.get("degree"),
                "field_of_study": row.get("field_of_study"),
                "description": row.get("description"),
                **_period(row.get("start_date"), row.get("end_date")),
            }
            for row in rows
        ]
    if logical == "certifications":
        return [
            {
                "name": row.get("name"),
                "issuer": row.get("issuer"),
                "issued": _iso(row.get("issued")),
                "expires": _iso(row.get("expires")),
                "status": row.get("status"),
                "credential_url": row.get("credential_url"),
            }
            for row in rows
        ]
    if logical == "languages":
        return [
            {"name": row.get("name"), "proficiency": row.get("proficiency")}
            for row in rows
        ]
    if logical == "recommendations":
        return [
            {
                "author_name": row.get("author_name"),
                "author_headline": row.get("author_headline"),
                "relationship": row.get("relationship"),
                "written_on": _iso(row.get("written_on")),
                "content": row.get("content"),
            }
            for row in rows
        ]
    if logical == "interests":
        return [
            {
                "name": row.get("name"),
                "description": row.get("description"),
                "kind": row.get("kind"),
            }
            for row in rows
        ]
    if logical == "sources":
        return [
            {"url": row.get("source_url"), "label": row.get("source_label")}
            for row in rows
        ]
    raise KeyError(f"Unknown section {logical!r}")


def _facts(person: dict[str, Any], facts: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for fact in facts:
        value = person.get(fact["field"])
        if value in (None, ""):
            continue
        out.append(
            {
                "label": fact["label"],
                "value": f"{value}{fact.get('suffix', '')}",
            }
        )
    return out


def profile(
    service: DatasetService, config: dict[str, Any], *, slug: str
) -> dict[str, Any]:
    """Everything one profile page shows, in the configured section order."""
    if not SLUG_PATTERN.match(slug or ""):
        raise ProfileNotFoundError(slug)

    data = config["data"]
    namespace = data["namespace"]
    tables = data["tables"]

    people = ds.fetch_people(
        service,
        namespace=namespace,
        table=tables["people"],
        where=f"slug = {ds.sql_literal(slug)}",
        limit=1,
    )
    if not people:
        raise ProfileNotFoundError(slug)
    person = people[0]

    rows_by_table = {
        logical: ds.fetch_children(
            service,
            namespace=namespace,
            table=tables[logical],
            slugs=[slug],
            order_by="skill_name" if logical == "skills" else "seq",
        ).get(slug, [])
        for logical in CHILD_TABLES
    }

    sections = []
    for section in config["profile"]["sections"]:
        if not section["enabled"]:
            continue
        section_id = section["id"]
        items = (
            [person.get("about")]
            if section_id == "about" and person.get("about")
            else []
        )
        if section_id != "about":
            items = _section_items(section_id, rows_by_table.get(section_id, []))
        sections.append(
            {
                "id": section_id,
                "label": section["label"],
                "empty_text": section["empty_text"],
                "items": items,
            }
        )

    place = [person.get("country"), person.get("office") or person.get("city")]
    return {
        "slug": person.get("slug"),
        "full_name": person.get("full_name"),
        "headline": person.get("headline"),
        "quote": person.get("quote"),
        "photo_url": person.get("photo_url"),
        "organization": person.get("organization"),
        "country_code": person.get("country_code"),
        "place": [value for value in place if value],
        "public_profile_url": person.get("public_profile_url"),
        "facts": _facts(person, config["profile"]["facts"]),
        "sections": sections,
        "knowledge_graph": _knowledge_graph(config),
        "competency_queries": competency_queries_for_profile(slug),
    }


def related(
    service: DatasetService, config: dict[str, Any], *, slug: str, limit: int = 4
) -> dict[str, Any]:
    """Other people in the same facet value, for the column beside a profile."""
    data = config["data"]
    facet_field = config["search"]["facet_field"]
    people = ds.fetch_people(
        service,
        namespace=data["namespace"],
        table=data["tables"]["people"],
        where=f"slug = {ds.sql_literal(slug)}",
        limit=1,
    )
    if not people or not people[0].get(facet_field):
        return {"facet_field": facet_field, "value": None, "people": []}

    value = str(people[0][facet_field])
    same = ds.fetch_people(
        service,
        namespace=data["namespace"],
        table=data["tables"]["people"],
        where=(
            f"{facet_field} = {ds.sql_literal(value)} AND slug <> {ds.sql_literal(slug)}"
        ),
        limit=limit,
    )
    return {
        "facet_field": facet_field,
        "value": value,
        "people": [
            {
                "slug": row.get("slug"),
                "full_name": row.get("full_name"),
                "headline": row.get("headline"),
                "photo_url": row.get("photo_url"),
            }
            for row in same
        ],
    }
