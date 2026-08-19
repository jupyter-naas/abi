#!/usr/bin/env python3
"""Build the personnel demo instance graph via process pipelines.

Reads ``data/demo/person/*/index.json``, runs ActOfWorking / ActOfStudying
pipelines, and writes ``graphs/demo/personnel.ttl``.
"""

from __future__ import annotations

from pathlib import Path

from naas_abi_marketplace.domains.personnel.ontologies.modules.PersonnelOntology import (
    EmployeeRole,
    EmploymentRecord,
    EmploymentStatus,
    JobDescription,
    JobPosition,
)
from naas_abi_marketplace.domains.personnel.paths import (
    DEMO_GRAPH_DIR,
    DEMO_GRAPH_FILE,
    DEMO_SOURCE_DIR,
    ONTOLOGIES_DIR,
    PERSONNEL_ROOT,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
    ActOfStudyingPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
    ActOfWorkingPipelineParameters,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
    bind_graph_prefixes,
    individual_uri,
    slug,
    utc_now,
)
from naas_abi_marketplace.domains.personnel.sandbox.load_person_sources import (
    load_person_sources,
    sources_to_employees,
    sources_to_experiences,
    sources_to_profile_urls,
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")


def load_schema_graph() -> Graph:
    g = Graph()
    for path in sorted(ONTOLOGIES_DIR.rglob("*.ttl")):
        if "queries" in path.parts:
            continue
        g.parse(path, format="turtle")
        print(f"  schema  {path.relative_to(PERSONNEL_ROOT)}")
    return g


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
            creator="demo_graph_builder",
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
            creator="demo_graph_builder",
        )
        context.graph += record.rdf()
        context.graph.add(
            (URIRef(person._uri), PERSONNEL.hasEmploymentRecord, URIRef(record._uri))
        )

        position_uri = current_position.get(person.label or "")
        if position_uri is None:
            position = JobPosition(
                _uri=individual_uri(str(PERSONNEL), "JobPosition", f"{person_slug}-roster"),
                label=emp["job_title"],
                job_title=emp["job_title"],
                has_job_description=[desc._uri],
                created=utc_now(),
                creator="demo_graph_builder",
            )
            context.graph += position.rdf()
            position_uri = position._uri

            role = EmployeeRole(
                _uri=individual_uri(str(PERSONNEL), "EmployeeRole", f"{person_slug}-roster"),
                label=emp["job_title"],
                is_employee_role_of=[person._uri],
                has_job_position=[position_uri],
                created=utc_now(),
                creator="demo_graph_builder",
            )
            context.graph += role.rdf()
            context.graph.add(
                (URIRef(person._uri), PERSONNEL.hasEmployeeRole, URIRef(role._uri))
            )
            context.graph.add(
                (URIRef(position_uri), PERSONNEL.isJobPositionOf, URIRef(role._uri))
            )
        else:
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
            creator="demo_graph_builder",
        )
        context.graph += status.rdf()
        context.graph.add(
            (URIRef(person._uri), PERSONNEL.hasEmploymentStatus, URIRef(status._uri))
        )


def build_instances(source_dir: Path | None = None) -> Graph:
    """Emit demo individuals from ``data/demo/person/*/index.json`` via pipelines."""
    payloads = load_person_sources(source_dir or DEMO_SOURCE_DIR)
    employees = sources_to_employees(payloads)
    profile_urls = sources_to_profile_urls(payloads)
    experiences = sources_to_experiences(payloads)

    context = PersonnelGraphContext(creator="demo_graph_builder")
    working_cfg = ActOfWorkingPipelineConfiguration(
        triple_store=None, persist=False, context=context
    )
    studying_cfg = ActOfStudyingPipelineConfiguration(
        triple_store=None, persist=False, context=context
    )
    working_pipeline = ActOfWorkingPipeline(working_cfg)
    studying_pipeline = ActOfStudyingPipeline(studying_cfg)
    current_position: dict[str, str] = {}

    for item in experiences:
        first, last = item["person"]
        person_key = f"{first} {last}"

        if item["kind"] == "studying":
            studying_pipeline.run(
                ActOfStudyingPipelineParameters(
                    first_name=first,
                    last_name=last,
                    organization=item["organization"],
                    program=item["program"],
                    site=item["site"],
                    start=item["start"],
                    end=item["end"],
                    duration=item.get("duration"),
                    skills=item.get("skills") or [],
                    activities=item.get("activities"),
                    source_url=item.get("source"),
                )
            )
            continue

        profile_url = profile_urls.get(person_key)
        if not profile_url:
            raise KeyError(f"No profile URL for {person_key!r}")

        working_pipeline.run(
            ActOfWorkingPipelineParameters(
                first_name=first,
                last_name=last,
                organization=item["organization"],
                title=item["title"],
                site=item["site"],
                start=item["start"],
                end=item["end"],
                duration=item.get("duration"),
                mission_label=item["mission_label"],
                mission=item["mission"],
                contract_type=item.get("contract_type"),
                skills=item.get("skills") or [],
                source_url=profile_url,
                remuneration_amount=item.get("remuneration_amount"),
                remuneration_currency=item.get("remuneration_currency") or "EUR",
            )
        )

        roster = next(
            (
                e
                for e in employees
                if (e["first"], e["last"]) == item["person"]
                and item["organization"].lower() == "demo"
            ),
            None,
        )
        if roster and context.last_position_uri:
            current_position[person_key] = context.last_position_uri

    _add_employment_records(context, employees=employees, current_position=current_position)
    return context.graph


def build_and_write_demo_graph(source_dir: Path | None = None) -> Path:
    print("Loading ontology schema…")
    schema = load_schema_graph()

    print("Building demo individuals via process pipelines…")
    instances = build_instances(source_dir)

    out = Graph()
    out += schema
    out += instances
    bind_graph_prefixes(out)

    DEMO_GRAPH_DIR.mkdir(parents=True, exist_ok=True)
    out.serialize(destination=str(DEMO_GRAPH_FILE), format="turtle")

    print(
        f"\nWrote {DEMO_GRAPH_FILE.relative_to(PERSONNEL_ROOT)} "
        f"({len(schema)} schema + {len(instances)} instance triples)"
    )
    return DEMO_GRAPH_FILE


def main() -> None:
    build_and_write_demo_graph()


if __name__ == "__main__":
    main()
