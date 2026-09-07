"""Build technical RDF change events for the Cockpit Logs page."""

from __future__ import annotations

import uuid
from typing import Any

RDF_TYPE = "http://www.w3.org/1999/02/22-rdf-syntax-ns#type"
RDFS_LABEL = "http://www.w3.org/2000/01/rdf-schema#label"
ABI = "http://ontology.naas.ai/abi/"
PERSONNEL = "http://ontology.naas.ai/personnel/"
MUTATION_NAMESPACE = uuid.UUID("f64ee1e2-dc18-4c17-9513-f9ec63f29a2b")


def _triple(
    subject: Any,
    predicate: str,
    object_value: Any,
) -> dict[str, str] | None:
    if subject in (None, "") or object_value in (None, ""):
        return None
    return {
        "subject": str(subject),
        "predicate": predicate,
        "object": str(object_value),
    }


def _triples(*values: dict[str, str] | None) -> list[dict[str, str]]:
    return [value for value in values if value is not None]


def _dedupe_triples(triples: list[dict[str, str]]) -> list[dict[str, str]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, str]] = []
    for triple in triples:
        key = (triple["subject"], triple["predicate"], triple["object"])
        if key not in seen:
            seen.add(key)
            unique.append(triple)
    return unique


def _operation(record: dict, default_operation: str) -> str:
    operation = str(record.get("operation") or default_operation).lower()
    return operation if operation in {"insert", "delete"} else default_operation


def _mutation_process_id(
    record: dict,
    context_process_id: str,
    owner_person_id: str,
    owner_agent_id: str,
    server_ip: str,
    target_graph: str,
    started_at: str,
) -> str:
    explicit = record.get("mutation_process_id")
    if explicit:
        return str(explicit)
    seed = "|".join(
        (
            context_process_id,
            owner_person_id,
            owner_agent_id,
            server_ip,
            target_graph,
            started_at,
        )
    )
    return f"{PERSONNEL}GraphMutation/{uuid.uuid5(MUTATION_NAMESPACE, seed)}"


def _event(
    record: dict,
    context_process_id: Any,
    triples: list[dict[str, str]],
    *,
    owner_person_id: str,
    owner_person_label: str,
    owner_agent_id: str,
    owner_agent_label: str,
    server_site_id: str,
    server_label: str,
    server_ip: str,
    target_graph: str,
    target_graph_label: str,
    process_label: str,
    started_at: str,
    completed_at: str,
    default_operation: str,
    default_status: str,
) -> dict[str, Any] | None:
    if context_process_id in (None, ""):
        return None
    context_process_id = str(context_process_id)
    operation = _operation(record, default_operation)
    explicit_added = record.get("triples_added")
    explicit_deleted = record.get("triples_deleted")
    return {
        "process_id": _mutation_process_id(
            record,
            context_process_id,
            owner_person_id,
            owner_agent_id,
            server_ip,
            target_graph,
            started_at,
        ),
        "process_label": process_label,
        "source_process_id": context_process_id,
        "source_process_label": str(
            record.get("workingLabel")
            or record.get("studyingLabel")
            or context_process_id
        ),
        "type": operation,
        "status": str(record.get("mutation_status") or default_status),
        "triples_added": (
            explicit_added
            if isinstance(explicit_added, list)
            else triples if operation == "insert" else []
        ),
        "triples_deleted": (
            explicit_deleted
            if isinstance(explicit_deleted, list)
            else triples if operation == "delete" else []
        ),
        "started_at": started_at,
        "completed_at": completed_at,
        "owners": [
            {
                "entity_id": owner_person_id,
                "label": owner_person_label,
                "entity_type": "Person",
            },
            {
                "entity_id": owner_agent_id,
                "label": owner_agent_label,
                "entity_type": "Agent",
            },
        ],
        "server_site_id": server_site_id,
        "server_label": server_label,
        "server_ip": server_ip,
        "target_graph": target_graph,
        "target_graph_label": target_graph_label,
    }


def _working_event(work: dict, **mutation: str) -> dict[str, Any] | None:
    process = work.get("working")
    temporal = work.get("temporal")
    role = work.get("role")
    mission = work.get("mission")
    triples = _triples(
        _triple(work.get("person"), f"{PERSONNEL}hasActOfWorking", process),
        _triple(process, RDF_TYPE, f"{PERSONNEL}ActOfWorking"),
        _triple(process, RDFS_LABEL, work.get("workingLabel")),
        _triple(process, f"{PERSONNEL}forOrganization", work.get("org")),
        _triple(process, f"{ABI}occursIn", work.get("site")),
        _triple(process, f"{ABI}occupiesTemporalRegion", temporal),
        _triple(process, f"{PERSONNEL}hasContract", work.get("contract")),
        _triple(process, f"{ABI}realizes", role),
        _triple(process, f"{ABI}hasParticipant", work.get("remuneration")),
        _triple(temporal, f"{ABI}hasFirstInstant", work.get("firstInstant")),
        _triple(temporal, f"{ABI}hasLastInstant", work.get("lastInstant")),
        _triple(role, f"{PERSONNEL}hasJobPosition", work.get("position")),
        _triple(role, f"{PERSONNEL}hasMission", mission),
        _triple(mission, f"{PERSONNEL}isSourcedFrom", work.get("profile")),
    )
    return _event(work, process, triples, **mutation)


def _studying_event(study: dict, **mutation: str) -> dict[str, Any] | None:
    process = study.get("studying")
    enrollment = study.get("enrollment")
    triples = _triples(
        _triple(study.get("person"), f"{PERSONNEL}hasActOfStudying", process),
        _triple(process, RDF_TYPE, f"{PERSONNEL}ActOfStudying"),
        _triple(
            process,
            f"{PERSONNEL}forEducationalOrganization",
            study.get("org"),
        ),
        _triple(process, f"{ABI}occursIn", study.get("site")),
        _triple(
            process,
            f"{ABI}occupiesTemporalRegion",
            study.get("temporal"),
        ),
        _triple(process, f"{PERSONNEL}hasEnrollment", enrollment),
        _triple(
            study.get("person"),
            f"{PERSONNEL}hasStudentRole",
            study.get("role"),
        ),
        _triple(
            enrollment,
            f"{PERSONNEL}program_name",
            study.get("programName"),
        ),
    )
    return _event(study, process, triples, **mutation)


def build_ledger_log_rows(
    working_rows: list[dict] | None = None,
    studying_rows: list[dict] | None = None,
    *,
    owner_person_id: str,
    owner_person_label: str,
    owner_agent_id: str,
    owner_agent_label: str,
    server_site_id: str,
    server_label: str,
    server_ip: str,
    target_graph: str,
    target_graph_label: str,
    process_label: str,
    started_at: str,
    completed_at: str,
    default_operation: str = "insert",
    default_status: str = "succeeded",
) -> list[dict[str, Any]]:
    """Return one demo graph-mutation audit event per unique person."""
    events_by_person: dict[str, dict[str, Any]] = {}
    mutation = {
        "owner_person_id": owner_person_id,
        "owner_person_label": owner_person_label,
        "owner_agent_id": owner_agent_id,
        "owner_agent_label": owner_agent_label,
        "server_site_id": server_site_id,
        "server_label": server_label,
        "server_ip": server_ip,
        "target_graph": target_graph,
        "target_graph_label": target_graph_label,
        "process_label": process_label,
        "started_at": started_at,
        "completed_at": completed_at,
        "default_operation": default_operation,
        "default_status": default_status,
    }
    for record, builder in (
        *((record, _working_event) for record in working_rows or []),
        *((record, _studying_event) for record in studying_rows or []),
    ):
        event = builder(record, **mutation)
        if event is None:
            continue
        person_id = str(record.get("person") or event["source_process_id"])
        person_label = str(record.get("personLabel") or person_id)
        existing = events_by_person.get(person_id)
        if existing is None:
            event["process_id"] = _mutation_process_id(
                record,
                person_id,
                owner_person_id,
                owner_agent_id,
                server_ip,
                target_graph,
                started_at,
            )
            event.pop("source_process_id", None)
            event.pop("source_process_label", None)
            changed_key = (
                "triples_deleted" if event["type"] == "delete" else "triples_added"
            )
            person_triples = (
                _triples(
                    _triple(person_id, RDF_TYPE, f"{ABI}Person"),
                    _triple(person_id, RDFS_LABEL, person_label),
                )
                if record.get("person")
                else []
            )
            event[changed_key] = [*person_triples, *event[changed_key]]
            events_by_person[person_id] = event
            continue
        existing["triples_added"].extend(event["triples_added"])
        existing["triples_deleted"].extend(event["triples_deleted"])

    events = list(events_by_person.values())
    for event in events:
        event["triples_added"] = _dedupe_triples(event["triples_added"])
        event["triples_deleted"] = _dedupe_triples(event["triples_deleted"])
    events.sort(
        key=lambda event: (event["started_at"], event["process_id"]),
        reverse=True,
    )
    return events


build_ledger_log_entries = build_ledger_log_rows
