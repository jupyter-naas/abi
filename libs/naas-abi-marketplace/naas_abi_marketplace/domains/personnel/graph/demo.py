"""Build the personnel demo instance graph from ``data/demo/person`` JSON."""

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
from naas_abi_marketplace.domains.personnel.person_sources import (
    load_person_sources,
    payload_to_profile_source_parameters,
    sources_to_employees,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfStudyingPipeline import (
    ActOfStudyingPipeline,
    ActOfStudyingPipelineConfiguration,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfCertificationPipeline import (
    ActOfCertificationPipeline,
    ActOfCertificationPipelineConfiguration,
)
from naas_abi_marketplace.domains.personnel.pipelines.ActOfWorkingPipeline import (
    ActOfWorkingPipeline,
    ActOfWorkingPipelineConfiguration,
)
from naas_abi_marketplace.domains.personnel.pipelines.PersonProfilePipeline import (
    PersonProfilePipeline,
    PersonProfilePipelineConfiguration,
)
from naas_abi_marketplace.domains.personnel.pipelines.profile_from_source import (
    ProfileFromSourcePipelineParameters,
    WorkingRecordInput,
    apply_profile_source_payload,
)
from naas_abi_marketplace.domains.personnel.pipelines.utils.graph_builders import (
    PersonnelGraphContext,
    bind_graph_prefixes,
    individual_uri,
    slug,
    utc_now,
)
from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import XSD

PERSONNEL = Namespace("http://ontology.naas.ai/personnel/")


def load_schema_graph() -> Graph:
    graph = Graph()
    for path in sorted(ONTOLOGIES_DIR.rglob("*.ttl")):
        if "queries" in path.parts:
            continue
        graph.parse(path, format="turtle")
    return graph


def _add_employment_records(
    context: PersonnelGraphContext,
    *,
    employees: list[dict],
    current_position: dict[str, str],
    creator: str,
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
            creator=creator,
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
            creator=creator,
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
                creator=creator,
            )
            context.graph += position.rdf()
            position_uri = position._uri

            role = EmployeeRole(
                _uri=individual_uri(str(PERSONNEL), "EmployeeRole", f"{person_slug}-roster"),
                label=emp["job_title"],
                is_employee_role_of=[person._uri],
                has_job_position=[position_uri],
                created=utc_now(),
                creator=creator,
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
            creator=creator,
        )
        context.graph += status.rdf()
        context.graph.add(
            (URIRef(person._uri), PERSONNEL.hasEmploymentStatus, URIRef(status._uri))
        )


def _track_roster_position(
    *,
    params: ProfileFromSourcePipelineParameters,
    employees: list[dict],
    context: PersonnelGraphContext,
    current_position: dict[str, str],
) -> None:
    person = params.person
    person_key = f"{person.first_name} {person.last_name}"
    roster = next(
        (
            e
            for e in employees
            if (e["first"], e["last"]) == (person.first_name, person.last_name)
        ),
        None,
    )
    if not roster:
        return
    for record in params.records:
        if not isinstance(record, WorkingRecordInput):
            continue
        if record.organization.lower() == "demo" and context.last_position_uri:
            current_position[person_key] = context.last_position_uri


def build_instance_graph(
    source_dir: Path | None = None,
    *,
    creator: str = "demo_person_graph",
) -> Graph:
    """Register every demo ``index.json`` via ``register_profile_from_source`` logic."""
    root = source_dir or DEMO_SOURCE_DIR
    payloads = load_person_sources(root)
    employees = sources_to_employees(payloads)

    context = PersonnelGraphContext(creator=creator)
    pipeline_cfg = dict(triple_store=None, persist=False, context=context)
    working = ActOfWorkingPipeline(ActOfWorkingPipelineConfiguration(**pipeline_cfg))
    studying = ActOfStudyingPipeline(ActOfStudyingPipelineConfiguration(**pipeline_cfg))
    certification = ActOfCertificationPipeline(
        ActOfCertificationPipelineConfiguration(**pipeline_cfg)
    )
    profile_pipeline = PersonProfilePipeline(
        PersonProfilePipelineConfiguration(**pipeline_cfg)
    )

    current_position: dict[str, str] = {}
    for payload in payloads:
        params = payload_to_profile_source_parameters(payload)
        apply_profile_source_payload(
            params,
            context=context,
            working=working,
            studying=studying,
            profile_pipeline=profile_pipeline,
            certification=certification,
        )
        _track_roster_position(
            params=params,
            employees=employees,
            context=context,
            current_position=current_position,
        )

    _add_employment_records(
        context,
        employees=employees,
        current_position=current_position,
        creator=creator,
    )
    return context.graph


def write_demo_graph_file(
    source_dir: Path | None = None,
    *,
    output_path: Path | None = None,
    include_schema: bool = True,
    creator: str = "demo_person_graph",
) -> tuple[Path, int, int]:
    """Write ``graphs/demo/personnel.ttl`` (schema + instances by default).

    Returns ``(path, schema_triple_count, instance_triple_count)``.
    """
    schema = load_schema_graph() if include_schema else Graph()
    instances = build_instance_graph(source_dir, creator=creator)

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
