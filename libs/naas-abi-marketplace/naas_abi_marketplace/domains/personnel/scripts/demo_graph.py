"""Build the personnel demo graph: the employer's records over the people demo.

The people module's demo files (``intelligence/modules/people/data/demo/person``)
hold what each fictional person publishes. This module's own files
(``personnel/data/demo/person/<slug>/index.json``) hold what their employer
records about the same people, and nothing else reads them:

* ``employer``, ``service_line``, ``grade``: who employs the person, in which
  service line and at which grade;
* ``employments``: which of their acts of working are acts of employment, with
  the contract, job family and pay behind each. An entry names the act by the
  ``organization``, ``client`` and ``title`` of the people record, so it adds to
  that act rather than restating it;
* ``roster``: the employment record, job description and employment status.

``build_overlay_graph`` returns only those records - what goes to the personnel
named graph. ``write_demo_graph_file`` writes them together with the people
instances and both schemas, which is what the cockpit's exporter reads.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    ABI,
    individual_uri,
    slug,
    utc_now,
)
from naas_abi_marketplace.domains.intelligence.modules.people.scripts.demo_graph import (
    build_instance_graph as build_people_instance_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.scripts.demo_graph import (
    load_schema_graph as load_people_schema_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.utils.person_sources import (
    load_person_sources,
)
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    EmploymentRecord,
    EmploymentStatus,
    JobDescription,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PERSONNEL,
    PersonnelGraphContext,
    bind_graph_prefixes,
)
from naas_abi_marketplace.domains.personnel.utils.paths import (
    DEMO_GRAPH_FILE,
    DEMO_SOURCE_DIR,
    ONTOLOGIES_DIR,
    PEOPLE_DEMO_SOURCE_DIR,
    PERSONNEL_ROOT,
)
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import XSD


def _parse_date(value: str | None) -> date | None:
    return date.fromisoformat(value) if value else None


def load_schema_graph() -> Graph:
    """Both schemas: people (imported) and personnel."""
    graph = load_people_schema_graph()
    for path in sorted(ONTOLOGIES_DIR.rglob("*.ttl")):
        if "queries" in path.parts:
            continue
        graph.parse(path, format="turtle")
    return graph


def sources_to_employees(payloads: list[dict]) -> list[dict]:
    """Roster rows (one per person) from the ``roster`` block of each personnel file."""
    seen: set[tuple[str, str]] = set()
    employees: list[dict] = []
    for payload in payloads:
        person = payload["person"]
        key = (person["first_name"], person["last_name"])
        roster = payload.get("roster")
        if not roster or key in seen:
            continue
        seen.add(key)
        employees.append(
            {
                "first": key[0],
                "last": key[1],
                "employee_id": roster["employee_id"],
                "job_title": roster["job_title"],
                "job_family": roster["job_family"],
                "hire_date": _parse_date(roster["hire_date"]),
                "termination_date": _parse_date(roster.get("termination_date")),
                "status": roster["status"],
            }
        )
    return employees


def _add_employment_records(
    context: PersonnelGraphContext,
    *,
    employees: list[dict],
    current_position: dict[str, str],
) -> None:
    for emp in employees:
        person = context.ensure_person(emp["first"], emp["last"])
        person_slug = slug(emp["first"], emp["last"])

        desc = JobDescription(
            _uri=individual_uri(
                str(PERSONNEL), "JobDescription", f"{person_slug}-{emp['employee_id']}"
            ),
            label=f"{emp['job_title']} - {emp['job_family']}",
            created=utc_now(),
            creator=context.creator,
        )
        context.graph += desc.rdf()

        record = EmploymentRecord(
            _uri=individual_uri(str(PERSONNEL), "EmploymentRecord", emp["employee_id"]),
            label=f"Employment record {emp['employee_id']}",
            employee_id=emp["employee_id"],
            hire_date=emp["hire_date"],
            termination_date=emp.get("termination_date"),
            is_employment_record_of=[person._uri],
            created=utc_now(),
            creator=context.creator,
        )
        context.graph += record.rdf()
        context.graph.add(
            (URIRef(person._uri), PERSONNEL.hasEmploymentRecord, URIRef(record._uri))
        )

        position_uri = current_position.get(person.label or "")
        if position_uri is not None:
            context.graph.add(
                (URIRef(position_uri), PERSONNEL.hasJobDescription, URIRef(desc._uri))
            )
            context.graph.add(
                (
                    URIRef(position_uri),
                    PERSONNEL.job_family,
                    Literal(emp["job_family"], datatype=XSD.string),
                )
            )

        status = EmploymentStatus(
            _uri=individual_uri(str(PERSONNEL), "EmploymentStatus", person_slug),
            label=emp["status"],
            status_value=emp["status"],
            is_employment_status_of=[person._uri],
            created=utc_now(),
            creator=context.creator,
        )
        context.graph += status.rdf()
        context.graph.add(
            (URIRef(person._uri), PERSONNEL.hasEmploymentStatus, URIRef(status._uri))
        )


def build_overlay_graph(
    source_dir: Path | None = None,
    *,
    creator: str = "demo_personnel_graph",
) -> Graph:
    """The employer's records for every personnel demo file, and nothing the people graph holds."""
    payloads = load_person_sources(source_dir or DEMO_SOURCE_DIR)
    context = PersonnelGraphContext(creator=creator)
    current_position: dict[str, str] = {}

    for payload in payloads:
        person_data = payload["person"]
        person = context.ensure_person(
            person_data["first_name"], person_data["last_name"]
        )
        employer = context.ensure_org(payload["employer"])

        # Employment comes first, so the service line below can attach to the
        # employee roles it creates.
        for employment in payload.get("employments") or []:
            client = (
                context.ensure_org(employment["client"])
                if employment.get("client")
                else None
            )
            context.add_employment(
                person=person,
                org=context.ensure_org(employment["organization"]),
                title=employment["title"],
                client=client,
                contract_type=employment.get("contract_type"),
                job_family=employment.get("job_family"),
                remuneration_amount=employment.get("remuneration_amount"),
                remuneration_currency=employment.get("remuneration_currency") or "EUR",
            )
            if context.last_position_uri:
                current_position[person.label or ""] = context.last_position_uri

        context.set_employer(person, employer)
        if payload.get("service_line"):
            line = context.ensure_service_line(payload["service_line"], employer)
            context.graph.add(
                (URIRef(line._uri), ABI.hasMemberPart, URIRef(person._uri))
            )
            for role in context.graph.objects(
                URIRef(person._uri), PERSONNEL.hasEmployeeRole
            ):
                context.graph.add((role, PERSONNEL.inServiceLine, URIRef(line._uri)))
        if payload.get("grade"):
            context.ensure_grade(payload["grade"], person)

    _add_employment_records(
        context,
        employees=sources_to_employees(payloads),
        current_position=current_position,
    )
    return context.graph


def write_demo_graph_file(
    source_dir: Path | None = None,
    *,
    people_source_dir: Path | None = None,
    output_path: Path | None = None,
    include_schema: bool = True,
    creator: str = "demo_personnel_graph",
) -> tuple[Path, int, int]:
    """Write ``graphs/demo/personnel.ttl``: people instances, personnel records, schemas.

    Returns ``(path, schema_triple_count, instance_triple_count)``.
    """
    schema = load_schema_graph() if include_schema else Graph()
    instances = Graph()
    instances += build_people_instance_graph(
        people_source_dir or PEOPLE_DEMO_SOURCE_DIR, creator=creator
    )
    instances += build_overlay_graph(source_dir, creator=creator)

    combined = Graph()
    combined += schema
    combined += instances
    bind_graph_prefixes(combined)

    destination = output_path or DEMO_GRAPH_FILE
    destination.parent.mkdir(parents=True, exist_ok=True)
    combined.serialize(destination=str(destination), format="turtle")
    return destination, len(schema), len(instances)


def schema_relative_paths() -> list[Path]:
    return [
        path.relative_to(PERSONNEL_ROOT)
        for path in sorted(ONTOLOGIES_DIR.rglob("*.ttl"))
        if "queries" not in path.parts
    ]
