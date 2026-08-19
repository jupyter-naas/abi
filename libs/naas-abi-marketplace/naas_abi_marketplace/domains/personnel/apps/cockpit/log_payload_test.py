from naas_abi_marketplace.domains.personnel.apps.cockpit.log_payload import (
    ABI,
    PERSONNEL,
    RDF_TYPE,
    build_ledger_log_rows,
)

MUTATION = {
    "owner_person_id": f"{ABI}Person/alice-dupont",
    "owner_person_label": "Alice Dupont",
    "owner_agent_id": f"{ABI}Agent/demo-agent",
    "owner_agent_label": "Demo Agent",
    "server_site_id": f"{PERSONNEL}Site/local-development",
    "server_label": "Local development server",
    "server_ip": "127.0.0.1",
    "target_graph": "http://ontology.naas.ai/graph/personnel",
    "target_graph_label": "Personnel graph",
    "process_label": "Graph mutation",
    "started_at": "2026-08-19T15:30:00+00:00",
    "completed_at": "2026-08-19T15:30:01+00:00",
}


def test_working_process_is_an_insert_with_rdf_triples() -> None:
    process = f"{PERSONNEL}working-1"
    person = f"{PERSONNEL}person-1"

    events = build_ledger_log_rows(
        [
            {
                "person": person,
                "personLabel": "Ada Lovelace",
                "working": process,
                "workingLabel": "Engineer at Naas",
                "org": f"{PERSONNEL}organization-1",
                "site": f"{PERSONNEL}site-1",
                "siteLabel": "Paris",
                "temporal": f"{PERSONNEL}temporal-1",
                "temporalStart": "2025-01-01",
                "temporalEnd": "2025-12-31",
            }
        ],
        **MUTATION,
    )

    assert events[0]["process_id"].startswith(f"{PERSONNEL}GraphMutation/")
    assert events[0]["process_label"] == "Graph mutation"
    assert "affected_person_id" not in events[0]
    assert "affected_person_label" not in events[0]
    assert "source_process_id" not in events[0]
    assert events[0]["type"] == "insert"
    assert events[0]["status"] == "succeeded"
    assert events[0]["owners"] == [
        {
            "entity_id": MUTATION["owner_person_id"],
            "label": "Alice Dupont",
            "entity_type": "Person",
        },
        {
            "entity_id": MUTATION["owner_agent_id"],
            "label": "Demo Agent",
            "entity_type": "Agent",
        },
    ]
    assert events[0]["server_site_id"] == MUTATION["server_site_id"]
    assert events[0]["server_label"] == MUTATION["server_label"]
    assert events[0]["server_ip"] == MUTATION["server_ip"]
    assert events[0]["target_graph"] == MUTATION["target_graph"]
    assert events[0]["target_graph_label"] == MUTATION["target_graph_label"]
    assert events[0]["started_at"] == MUTATION["started_at"]
    assert events[0]["completed_at"] == MUTATION["completed_at"]
    assert events[0]["triples_deleted"] == []
    assert {
        "subject": person,
        "predicate": RDF_TYPE,
        "object": f"{ABI}Person",
    } in events[0]["triples_added"]
    assert {
        "subject": process,
        "predicate": RDF_TYPE,
        "object": f"{PERSONNEL}ActOfWorking",
    } in events[0]["triples_added"]
    assert {
        "subject": process,
        "predicate": f"{ABI}occursIn",
        "object": f"{PERSONNEL}site-1",
    } in events[0]["triples_added"]


def test_delete_operation_places_triples_in_deleted_column() -> None:
    process = f"{PERSONNEL}studying-1"

    events = build_ledger_log_rows(
        studying_rows=[
            {
                "operation": "delete",
                "person": f"{PERSONNEL}person-1",
                "studying": process,
            }
        ],
        **MUTATION,
    )

    assert events[0]["type"] == "delete"
    assert events[0]["triples_added"] == []
    assert events[0]["triples_deleted"]


def test_explicit_change_triples_are_preserved() -> None:
    explicit = [{"subject": "s", "predicate": "p", "object": "o"}]

    events = build_ledger_log_rows(
        [{"working": "process-1", "triples_added": explicit}],
        **MUTATION,
    )

    assert events[0]["triples_added"] == explicit


def test_processes_for_same_person_are_combined_into_one_event() -> None:
    person = f"{PERSONNEL}person-1"

    events = build_ledger_log_rows(
        [
            {"person": person, "personLabel": "Ada", "working": "working-1"},
            {"person": person, "personLabel": "Ada", "working": "working-2"},
        ],
        **MUTATION,
    )

    assert len(events) == 1
    objects = {triple["object"] for triple in events[0]["triples_added"]}
    assert {"working-1", "working-2"}.issubset(objects)
