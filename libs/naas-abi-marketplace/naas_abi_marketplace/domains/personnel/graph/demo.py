"""Build the personnel demo graph: the employer's records over the people demo.

The demo person files are the people module's (``data/demo/person``). The
people graph registers what they publish; this module adds what their employer
records, for the organization each profile names:

* that it employs the person, the service line and grade it gives them;
* each of their acts of working for it, as an act of employment (employee
  role, job position, contract);
* when a file carries an HR ``roster`` block, the employment record, job
  description and employment status it lists.

``build_overlay_graph`` returns only those records - what goes to the personnel
named graph. ``write_demo_graph_file`` writes them together with the people
instances and both schemas, which is what the cockpit's exporter reads.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from naas_abi_marketplace.domains.intelligence.modules.people.graph.demo import (
    build_instance_graph as build_people_instance_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.graph.demo import (
    load_schema_graph as load_people_schema_graph,
)
from naas_abi_marketplace.domains.intelligence.modules.people.person_sources import (
    load_person_sources,
)
from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    EmploymentRecord,
    EmploymentStatus,
    JobDescription,
)
from naas_abi_marketplace.domains.personnel.paths import (
    DEMO_GRAPH_FILE,
    DEMO_SOURCE_DIR,
    ONTOLOGIES_DIR,
    PERSONNEL_ROOT,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PERSONNEL,
    PersonnelGraphContext,
    bind_graph_prefixes,
)
from naas_abi_marketplace.domains.intelligence.modules.people.pipelines.utils.graph_builders import (
    ABI,
    individual_uri,
    slug,
    utc_now,
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
    """Roster rows (one per person) from the HR ``roster`` block of each payload."""
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
    """The employer's records for every demo person, and nothing the people graph holds."""
    payloads = load_person_sources(source_dir or DEMO_SOURCE_DIR)
    context = PersonnelGraphContext(creator=creator)
    current_position: dict[str, str] = {}

    for payload in payloads:
        profile = payload.get("profile") or {}
        employer_label = profile.get("organization")
        if not employer_label:
            continue
        person_data = payload["person"]
        person = context.ensure_person(
            person_data["first_name"], person_data["last_name"]
        )
        employer = context.ensure_org(employer_label)

        # Acts of working for the employer the profile names are acts of
        # employment. Employment comes first, so the service line below can
        # attach to the employee roles it creates.
        for record in payload.get("records") or []:
            if record.get("process_type") != "ActOfWorking":
                continue
            if record.get("organization") != employer_label:
                continue
            client = (
                context.ensure_org(record["client"]) if record.get("client") else None
            )
            context.add_employment(
                person=person,
                org=employer,
                title=record["title"],
                client=client,
                contract_type=record.get("contract_type")
                or record.get("employment_type"),
                remuneration_amount=record.get("remuneration_amount"),
                remuneration_currency=record.get("remuneration_currency") or "EUR",
            )
            if context.last_position_uri:
                current_position[person.label or ""] = context.last_position_uri

        context.set_employer(person, employer)
        if profile.get("service_line"):
            line = context.ensure_service_line(profile["service_line"], employer)
            context.graph.add(
                (URIRef(line._uri), ABI.hasMemberPart, URIRef(person._uri))
            )
            for role in context.graph.objects(
                URIRef(person._uri), PERSONNEL.hasEmployeeRole
            ):
                context.graph.add((role, PERSONNEL.inServiceLine, URIRef(line._uri)))
        if profile.get("grade"):
            context.ensure_grade(profile["grade"], person)

    _add_employment_records(
        context,
        employees=sources_to_employees(payloads),
        current_position=current_position,
    )
    return context.graph


def write_demo_graph_file(
    source_dir: Path | None = None,
    *,
    output_path: Path | None = None,
    include_schema: bool = True,
    creator: str = "demo_personnel_graph",
) -> tuple[Path, int, int]:
    """Write ``graphs/demo/personnel.ttl``: people instances, personnel records, schemas.

    Returns ``(path, schema_triple_count, instance_triple_count)``.
    """
    schema = load_schema_graph() if include_schema else Graph()
    instances = Graph()
    instances += build_people_instance_graph(source_dir, creator=creator)
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
