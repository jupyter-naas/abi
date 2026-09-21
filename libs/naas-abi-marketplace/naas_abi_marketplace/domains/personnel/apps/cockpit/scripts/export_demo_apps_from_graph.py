#!/usr/bin/env python3
"""Run personnel SPARQL queries against the demo TTL and write app JSON.

Reads ``graphs/demo/personnel.ttl``, executes competency queries, then:

1. Writes a **structure reference copy** under ``apps/cockpit/data/`` (committed).
2. Publishes the **runtime datasets** to ObjectStorage at
   ``personnel/apps/cockpit/data/`` (fs: ``.abi/storage/datastore/...``).

The dev server reads from ObjectStorage only. Regenerate with ``make demo-data``.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from naas_abi_marketplace.domains.personnel.apps.cockpit.config_loader import (
    load_config,
    load_default_entity,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.data_store import (
    publish_data_tree,
    runtime_storage_prefix,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_payload import (
    build_graph_page_payload,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.graph_query import (
    load_query_templates,
    query_source_rows,
    roster_and_kpis,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.log_payload import (
    build_ledger_log_rows,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.paths import (
    DATA_ROOT,
    DEFAULT_ENTITY_ID,
    DEFAULT_ENTITY_SLUG,
    ENTITY_DATA,
    GRAPH_FILE,
)
from naas_abi_marketplace.domains.personnel.apps.cockpit.processes_payload import (
    build_processes_page_payload,
)
from naas_abi_marketplace.domains.personnel.paths import PERSONNEL_ROOT
from rdflib import Graph

SCHEMA = "1.0"
ENTITY_ID = DEFAULT_ENTITY_ID


def _now_version() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d %H:%M")


def _envelope(records: list, **extra) -> dict:
    body = {
        "schema_version": SCHEMA,
        "data_version": _now_version(),
        "entity_id": ENTITY_ID,
        "source": str(GRAPH_FILE.relative_to(PERSONNEL_ROOT)),
        "records": records,
    }
    body.update(extra)
    return body


def _dump(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"  wrote {path.relative_to(PERSONNEL_ROOT)}")


def main() -> None:
    if not GRAPH_FILE.exists():
        raise SystemExit(
            f"Missing {GRAPH_FILE}. Run make demo-graph first."
        )

    print(f"Loading {GRAPH_FILE.relative_to(PERSONNEL_ROOT)}…")
    graph = Graph()
    graph.parse(GRAPH_FILE, format="turtle")
    print(f"  {len(graph)} triples")

    templates = load_query_templates()
    print(f"  {len(templates)} SPARQL templates")

    # --- SPARQL query rows (in memory → page datasets) --------------------
    print("queries/")
    source_rows = query_source_rows(graph, templates)

    # --- page datasets ------------------------------------------------------
    print(f"data/entities/{ENTITY_ID}/")
    org_label = load_default_entity().get("organizationLabel") or "Demo"
    roster_rows, roster_source, kpis = roster_and_kpis(
        source_rows, org_label=org_label
    )
    print(f"  roster: {len(roster_rows)} rows from {roster_source}")

    _dump(
        ENTITY_DATA / "dashboard" / "kpis.json",
        _envelope([], kpis=kpis),
    )
    _dump(ENTITY_DATA / "dashboard" / "roster.json", _envelope(roster_rows))

    graph_payload = build_graph_page_payload(
        roster_rows,
        source_rows.get("find_working_experiences", []),
        source_rows.get("find_skills_developed", []),
        source_rows.get("find_educations", []),
    )
    _dump(
        ENTITY_DATA / "graph" / "index.json",
        _envelope([], **graph_payload),
    )
    logs_config = load_config()["logs"]
    mutation_started_at = datetime.now(UTC).isoformat()
    mutation_completed_at = datetime.now(UTC).isoformat()
    data_version = _now_version()
    _dump(
        ENTITY_DATA / "processes" / "processes.json",
        build_processes_page_payload(entity_id=ENTITY_ID, data_version=data_version),
    )
    _dump(
        ENTITY_DATA / "logs" / "ledger.json",
        _envelope(
            build_ledger_log_rows(
                source_rows.get("find_working_experiences", []),
                source_rows.get("find_educations", []),
                owner_person_id=logs_config["owner"]["person"]["entity_id"],
                owner_person_label=logs_config["owner"]["person"]["display_name"],
                owner_agent_id=logs_config["owner"]["agent"]["entity_id"],
                owner_agent_label=logs_config["owner"]["agent"]["display_name"],
                server_site_id=logs_config["server"]["site_id"],
                server_label=logs_config["server"]["display_name"],
                server_ip=logs_config["server"]["ip_address"],
                target_graph=logs_config["target_graph"],
                target_graph_label=logs_config["target_graph_label"],
                process_label=logs_config["process_label"],
                started_at=mutation_started_at,
                completed_at=mutation_completed_at,
                default_operation=logs_config["default_operation"],
                default_status=logs_config["default_status"],
            )
        ),
    )

    page_datasets = {
        "dashboard": [
            "dashboard/kpis.json",
            "dashboard/roster.json",
        ],
        "graph": [
            "graph/index.json",
        ],
        "processes": [
            "processes/processes.json",
        ],
        "logs": [
            "logs/ledger.json",
        ],
    }
    pages = {
        page["page_id"]: page_datasets[page["page_id"]]
        for page in load_config()["app"]["pages"]
        if page.get("enabled") and page["page_id"] in page_datasets
    }

    _dump(
        ENTITY_DATA / "manifest.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entity_id": ENTITY_ID,
            "graph": str(GRAPH_FILE.relative_to(PERSONNEL_ROOT)),
            "datasets": {"pages": pages},
        },
    )
    _dump(
        DATA_ROOT / "globals" / "entities.json",
        {
            "schema_version": SCHEMA,
            "data_version": data_version,
            "entities": [
                {
                    "entity_id": ENTITY_ID,
                    "display_name": "Demo",
                    "url_slug": DEFAULT_ENTITY_SLUG,
                    "entity_type": "organization",
                    "is_default": True,
                    "organizationLabel": "Demo",
                    "organization_uri": "http://ontology.naas.ai/abi/Organization/demo",
                }
            ],
        },
    )
    print("done.")
    published = publish_data_tree(DATA_ROOT)
    print(
        f"  published {len(published)} files to object storage "
        f"({runtime_storage_prefix()}/)"
    )


if __name__ == "__main__":
    main()
