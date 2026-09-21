#!/usr/bin/env python3
"""Run the personnel competency queries and write the People Search datasets.

    graph (ontology-backed)  ->  SPARQL  ->  dataset service  ->  app

Reads ``graphs/demo/personnel.ttl`` by default. Every value passes the privacy
gate before it is written, so an email address or a phone number cannot slip
out through a headline or a mission. Contact details go in the three contact
columns of ``people`` only, are checked for shape there, and are left empty
unless the instance sets ``privacy.publish_contact_details``.

``--config`` exports into another instance's namespace and tables, from
whichever graph that instance is built from:

    python -m …apps.people.scripts.export_people_from_graph
    python -m …apps.people.scripts.export_people_from_graph \
        --config path/to/instance/config.yaml \
        --graph  path/to/instance/graphs/personnel.ttl
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

from naas_abi_core.services.dataset.DatasetService import DatasetService
from naas_abi_marketplace.domains.personnel.apps.people.scripts import datasets as ds
from naas_abi_marketplace.domains.personnel.apps.people.config_loader import load_config
from naas_abi_marketplace.domains.personnel.apps.people.scripts.text import search_text
from naas_abi_marketplace.domains.personnel.apps.people.scripts import sparql_queries as sq
from naas_abi_marketplace.domains.personnel.paths import DEMO_GRAPH_FILE, PERSONNEL_ROOT
from rdflib import Graph

# The interactive query runner caps its rows (sq.DEFAULT_ROW_LIMIT) to keep a page
# fast. An export must not: a cap there drops rows without a word, and the app
# then shows a directory that is quietly missing people's skills.
ROW_LIMIT = 1_000_000

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
DIGIT_RUN_RE = re.compile(r"[\d][\d\s().-]{7,}")
URL_RE = re.compile(r"^https?://", re.IGNORECASE)
# The columns of the people table that exist to carry contact details. They are
# exempt from the gate below, which would refuse them by design, and are held
# to their own shape instead.
CONTACT_COLUMNS = ("email", "phone", "linkedin_url")
# Built from fields that are gated themselves; see ``gate_rows``.
DERIVED_COLUMNS = {("people", "search_text")}
CONTACT_SHAPES = {
    "email": re.compile(r"^[\w.+-]+@[\w-]+(?:\.[\w-]+)+$"),
    "phone": re.compile(r"^\+?[\d][\d\s().-]{5,}$"),
    "linkedin_url": re.compile(
        r"^https://(?:[a-z]{2,3}\.)?linkedin\.com/\S+$", re.IGNORECASE
    ),
}

# A portrait path is stated relative to the domain root. The page is served out
# of web/, so that prefix comes off and what is left is what the browser asks
# for. An instance sets its own in ``data.portrait_prefix``.
APP_PREFIX = "apps/people/web/"


class PrivacyError(ValueError):
    """A value carries something a directory must not publish."""


def _has_long_digit_run(text: str) -> bool:
    # Nine digits or more. A year range such as "2018-2021" has eight, so it
    # passes; a phone number does not.
    return any(
        sum(char.isdigit() for char in match) >= 9
        for match in DIGIT_RUN_RE.findall(text)
    )


def check_privacy(value: Any, *, where: str, config: dict[str, Any]) -> Any:
    """Refuse to export an email address or a phone number."""
    if not isinstance(value, str) or not value:
        return value
    privacy = config.get("privacy") or {}
    if privacy.get("reject_emails", True) and EMAIL_RE.search(value):
        raise PrivacyError(f"{where} contains an email address: {value!r}")
    # A web address is not a phone number. Image CDNs and credential registries
    # put long numeric ids in their paths, and refusing those would refuse every
    # portrait rather than protect anyone.
    if URL_RE.match(value):
        return value
    if privacy.get("reject_long_digit_runs", True) and _has_long_digit_run(value):
        raise PrivacyError(
            f"{where} contains what looks like a phone number: {value!r}"
        )
    return value


def check_contact(
    column: str, value: Any, *, where: str, config: dict[str, Any]
) -> Any:
    """Publish a contact detail only when the instance opts in, and only if it is one.

    An instance that has not set ``privacy.publish_contact_details`` gets the
    column empty rather than an error: the graph may well hold the detail, and
    whether to show it is a decision about the directory, not about the data.
    """
    if not isinstance(value, str) or not value:
        return None
    privacy = config.get("privacy") or {}
    if not privacy.get("publish_contact_details", False):
        return None
    if not CONTACT_SHAPES[column].match(value.strip()):
        raise PrivacyError(f"{where} is not a well-formed {column}: {value!r}")
    return value.strip()


def load_queries() -> dict[str, str]:
    return sq.load_queries()


def _strip_named_graph(sparql: str) -> str:
    return sq.strip_named_graph(sparql)


class TruncatedExportError(RuntimeError):
    """A query returned as many rows as its limit allows: some were cut off."""


def run_query(graph: Graph, template: str, **arguments: object) -> list[dict[str, Any]]:
    rows = sq.run_query(graph, template, **arguments)
    limit = arguments.get("limit")
    if isinstance(limit, int) and len(rows) >= limit:
        raise TruncatedExportError(
            f"a query returned {len(rows)} rows, its limit: the export would be "
            "missing rows. Raise ROW_LIMIT."
        )
    return rows


def _photo_url(row: dict[str, Any], prefix: str = APP_PREFIX) -> str | None:
    url = row.get("portraitUrl")
    if url:
        return url
    path = row.get("portraitPath")
    if not path:
        return None
    if path.startswith(prefix):
        return path[len(prefix) :]
    return path


def _int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _date(value: Any) -> str | None:
    if value in (None, ""):
        return None
    return str(value)[:10]


def build_rows(graph: Graph, config: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """Every table's rows, keyed by logical table name."""
    queries = load_queries()
    portrait_prefix = config["data"].get("portrait_prefix") or APP_PREFIX

    directory = run_query(graph, queries["find_people_directory"], limit=ROW_LIMIT)
    # Everyone the directory returns is keyed by their slug; a person with none
    # has not been given one, and cannot be addressed by a profile URL.
    people_by_slug = {row["slug"]: row for row in directory if row.get("slug")}
    slugs = set(people_by_slug)

    def by_person(
        query_name: str, **arguments: object
    ) -> dict[str, list[dict[str, Any]]]:
        grouped: dict[str, list[dict[str, Any]]] = {}
        for row in run_query(graph, queries[query_name], limit=ROW_LIMIT, **arguments):
            slug = row.get("slug")
            if slug in slugs:
                grouped.setdefault(slug, []).append(row)
        return grouped

    skills = by_person("find_person_skills")
    certifications = by_person("find_certifications")
    languages = by_person("find_languages")
    recommendations = by_person("find_recommendations")
    interests = by_person("find_interests")

    working = run_query(graph, queries["find_working_experiences"], limit=ROW_LIMIT)
    studying = run_query(graph, queries["find_educations"], limit=ROW_LIMIT)
    by_label = {row["personLabel"]: slug for slug, row in people_by_slug.items()}

    experience: dict[str, list[dict[str, Any]]] = {}
    for row in working:
        slug = by_label.get(row.get("personLabel"))
        if slug:
            experience.setdefault(slug, []).append(row)
    education: dict[str, list[dict[str, Any]]] = {}
    for row in studying:
        slug = by_label.get(row.get("personLabel"))
        if slug:
            education.setdefault(slug, []).append(row)

    tables: dict[str, list[dict[str, Any]]] = {name: [] for name in ds.TABLES}

    for slug, row in sorted(people_by_slug.items()):
        person_experience = sorted(
            experience.get(slug, []),
            key=lambda item: (
                item.get("temporalStart") or "",
                item.get("orgLabel") or "",
            ),
            reverse=True,
        )
        person_education = sorted(
            education.get(slug, []),
            key=lambda item: item.get("temporalStart") or "",
            reverse=True,
        )
        person_skills = sorted(
            {
                item.get("skillLabel")
                for item in skills.get(slug, [])
                if item.get("skillLabel")
            }
        )

        group_index: dict[str, int] = {}
        for seq, item in enumerate(person_experience):
            organization = item.get("orgLabel") or ""
            title = item.get("roleLabel") or item.get("jobTitle")
            description = item.get("missionContent") or item.get("missionLabel")
            group_index.setdefault(organization, len(group_index))
            tables["experience"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "group_seq": group_index[organization],
                    "organization": organization or None,
                    "location": item.get("siteLabel"),
                    "title": title,
                    # A source that named the role but not what it involved
                    # leaves the mission equal to the title. Showing it twice
                    # would look like two facts where the source gave one.
                    "description": description if description != title else None,
                    "start_date": _date(item.get("temporalStart")),
                    "end_date": _date(item.get("temporalEnd")),
                    "duration_label": item.get("durationLabel"),
                }
            )

        for seq, item in enumerate(person_education):
            degree = item.get("degreeLabel")
            field = item.get("programName")
            tables["education"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "school": item.get("orgLabel"),
                    "degree": degree,
                    # The degree and the programme are one statement in the
                    # graph unless the source distinguished them. Repeating it
                    # in both columns reads as "Law, Law".
                    "field_of_study": field if field != degree else None,
                    "description": item.get("activitiesContent"),
                    "start_date": _date(item.get("temporalStart")),
                    "end_date": _date(item.get("temporalEnd")),
                }
            )

        for skill in person_skills:
            tables["skills"].append({"slug": slug, "skill_name": skill})

        for seq, item in enumerate(certifications.get(slug, [])):
            tables["certifications"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "name": item.get("certificationName"),
                    "issuer": item.get("issuerLabel"),
                    "issued": _date(item.get("issueDate")),
                    "expires": _date(item.get("expiryDate")),
                    "status": item.get("certificationStatus"),
                    "credential_url": item.get("credentialUrl"),
                }
            )

        for seq, item in enumerate(languages.get(slug, [])):
            tables["languages"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "name": item.get("languageName") or item.get("languageLabel"),
                    "proficiency": item.get("proficiencyLevel"),
                }
            )

        for seq, item in enumerate(recommendations.get(slug, [])):
            tables["recommendations"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "author_name": item.get("authorLabel"),
                    "author_headline": item.get("authorHeadline"),
                    "relationship": item.get("relationshipLabel"),
                    "written_on": _date(item.get("recommendationDate")),
                    "content": item.get("recommendationContent"),
                }
            )

        for seq, item in enumerate(interests.get(slug, [])):
            tables["interests"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "name": item.get("interestName") or item.get("targetLabel"),
                    "description": item.get("interestDescription"),
                    "kind": item.get("interestKind"),
                }
            )

        source_urls: list[str] = []
        for candidate in [row.get("profileUrl")] + [
            item.get("sourceUrl") for item in person_experience
        ]:
            if candidate and candidate not in source_urls:
                source_urls.append(candidate)
        for seq, url in enumerate(source_urls):
            # A source is only a published profile if it is on the web. An
            # internal directory is often sourced from a file, and calling that
            # a published profile would be a claim the source never made.
            published = url.startswith(("http://", "https://"))
            tables["sources"].append(
                {
                    "slug": slug,
                    "seq": seq,
                    "source_url": url,
                    "source_label": "Published profile"
                    if published and seq == 0
                    else "Source",
                }
            )

        searchable = {
            "full_name": [row.get("personLabel") or ""],
            "headline": [row.get("headline") or ""],
            "about": [row.get("about") or ""],
            "service_line": [row.get("serviceLineLabel") or ""],
            "grade": [row.get("gradeValue") or ""],
            "office": [row.get("officeLabel") or "", row.get("cityName") or ""],
            "country": [row.get("countryName") or ""],
            "skills": person_skills,
            "experience": [
                value
                for item in person_experience
                for value in (
                    item.get("roleLabel") or "",
                    item.get("orgLabel") or "",
                    item.get("missionContent") or "",
                )
            ],
            "education": [
                value
                for item in person_education
                for value in (
                    item.get("orgLabel") or "",
                    item.get("degreeLabel") or "",
                    item.get("programName") or "",
                )
            ],
            "certifications": [
                value
                for item in certifications.get(slug, [])
                for value in (
                    item.get("certificationName") or "",
                    item.get("issuerLabel") or "",
                )
            ],
            "languages": [
                item.get("languageName") or "" for item in languages.get(slug, [])
            ],
            "interests": [
                item.get("interestName") or "" for item in interests.get(slug, [])
            ],
        }

        tables["people"].append(
            {
                "slug": slug,
                "full_name": row.get("personLabel"),
                "headline": row.get("headline"),
                "about": row.get("about"),
                "quote": row.get("quote"),
                "photo_url": _photo_url(row, portrait_prefix),
                "organization": row.get("organizationLabel"),
                "office": row.get("officeLabel"),
                "city": row.get("cityName"),
                "country": row.get("countryName"),
                "country_code": row.get("countryCode"),
                "service_line": row.get("serviceLineLabel"),
                "grade": row.get("gradeValue"),
                "years_of_experience": _int(row.get("yearsOfExperience")),
                "public_profile_url": row.get("profileUrl"),
                "email": row.get("emailAddress"),
                "phone": row.get("telephoneNumber"),
                "linkedin_url": row.get("linkedinUrl"),
                "search_text": search_text(searchable),
            }
        )

    gate_rows(tables, config)
    return tables


def gate_rows(tables: dict[str, list[dict[str, Any]]], config: dict[str, Any]) -> None:
    """Hold every value about to be published to the privacy gate.

    ``people.search_text`` is exempt: it is a bag of the unique words of fields
    that are each gated in their own column. Folding drops the punctuation that
    kept "2010, 2011, 2015 and 2018" apart, so a biography that merely lists
    years would read as a phone number. Nothing in it is a new claim.
    """
    for table_name, rows in tables.items():
        for index, table_row in enumerate(rows):
            for column, value in table_row.items():
                where = f"{table_name}[{index}].{column}"
                if table_name == "people" and column in CONTACT_COLUMNS:
                    table_row[column] = check_contact(
                        column, value, where=where, config=config
                    )
                elif (table_name, column) not in DERIVED_COLUMNS:
                    check_privacy(value, where=where, config=config)


def publish(
    service: DatasetService,
    config: dict[str, Any],
    tables: dict[str, list[dict[str, Any]]],
) -> None:
    data = config["data"]
    for logical, rows in tables.items():
        spec = ds.dataset_spec(
            logical, table=data["tables"][logical], namespace=data["namespace"]
        )
        ds.replace_rows(service, spec, rows)
        print(f"  {data['namespace']}.{spec.name}: {len(rows)} rows", flush=True)


def load_graph(ttl_path: Path) -> Graph:
    graph = Graph()
    graph.parse(ttl_path, format="turtle")
    return graph


def default_dataset_service() -> DatasetService:
    """The engine's service when this runs inside it, else a local warehouse.

    The exporter has to work as a plain script - that is how the Makefile runs
    it - so "no module initialized" is the normal case, not an error.
    """
    from naas_abi_marketplace.domains.personnel.apps.people.api.service import (
        dataset_service,
    )

    return dataset_service()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--graph",
        type=Path,
        default=DEMO_GRAPH_FILE,
        help="TTL file to read (default: the committed demo graph)",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=None,
        help="config.yaml of the instance to export into (default: this app's)",
    )
    parser.add_argument(
        "--catalog",
        default=None,
        help="DuckLake catalog, e.g. sqlite:storage/datasets.sqlite. "
        "Without it, the engine's dataset service is used.",
    )
    parser.add_argument(
        "--data-path", default=None, help="Warehouse path for --catalog"
    )
    args = parser.parse_args(argv)

    config = load_config(args.config)
    print(f"Reading {args.graph}", flush=True)
    graph = load_graph(args.graph)

    print("Running competency queries…", flush=True)
    tables = build_rows(graph, config)

    if args.catalog:
        from naas_abi_core.services.dataset.DatasetFactory import DatasetFactory

        service = DatasetFactory.DatasetServiceDuckLake(
            args.catalog, args.data_path or "storage/datasets/"
        )
    else:
        service = default_dataset_service()

    print("Writing datasets…", flush=True)
    publish(service, config, tables)
    print(
        f"Done: {len(tables['people'])} people from "
        f"{args.graph.relative_to(PERSONNEL_ROOT) if args.graph.is_relative_to(PERSONNEL_ROOT) else args.graph}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
